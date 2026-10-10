import pytest

from backend.agent_task_event_analytics import (
    InvalidAgentTaskRecoveryDecisionAuditError,
    LLMAgentTaskRecoveryDecisionAuditService,
    RECOVERY_ACTION_REFRESH_CONTEXT,
    RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
    AgentTaskRecoveryRecommendation,
)
from backend.agent_task_events import InMemoryAgentTaskEventStore, LLMAgentTaskEventQueryService, LLMAgentTaskEventService


def _services():
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    audit_service = LLMAgentTaskRecoveryDecisionAuditService(event_service=event_service, query_service=query_service)
    return event_service, audit_service


def _recommendation(task_id="task-1", **overrides):
    fields = dict(
        task_id=task_id,
        recommended_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        confidence=0.75,
        reason="context refresh succeeded in 3 of 4 prior attempts",
        supporting_recovery_ids=("recovery-1", "recovery-2"),
        blocking_conditions=(),
        failure_event_id="failure-event-1",
    )
    fields.update(overrides)
    return AgentTaskRecoveryRecommendation(**fields)


# --- record recommendation --------------------------------------------------------------------


def test_record_recommendation():
    _, audit_service = _services()

    audit = audit_service.record("task-1", _recommendation())

    assert audit.task_id == "task-1"
    assert audit.recommended_action == RECOVERY_ACTION_REFRESH_CONTEXT
    assert audit.confidence == 0.75
    assert audit.failure_event_id == "failure-event-1"
    assert audit.created_at is not None


def test_record_rejects_blank_task_id():
    _, audit_service = _services()

    with pytest.raises(InvalidAgentTaskRecoveryDecisionAuditError):
        audit_service.record("", _recommendation())


def test_record_rejects_non_recommendation_argument():
    _, audit_service = _services()

    with pytest.raises(InvalidAgentTaskRecoveryDecisionAuditError):
        audit_service.record("task-1", "not-a-recommendation")


def test_record_rejects_task_id_mismatch():
    _, audit_service = _services()

    with pytest.raises(InvalidAgentTaskRecoveryDecisionAuditError):
        audit_service.record("task-2", _recommendation(task_id="task-1"))


# --- preserve supporting recovery IDs -----------------------------------------------------------------


def test_supporting_recovery_ids_are_preserved():
    _, audit_service = _services()

    audit = audit_service.record(
        "task-1", _recommendation(supporting_recovery_ids=("recovery-a", "recovery-b", "recovery-c"))
    )

    assert audit.supporting_recovery_ids == ("recovery-a", "recovery-b", "recovery-c")


def test_empty_supporting_recovery_ids_are_preserved():
    _, audit_service = _services()

    audit = audit_service.record("task-1", _recommendation(supporting_recovery_ids=()))

    assert audit.supporting_recovery_ids == ()


# --- preserve blocking conditions/reason --------------------------------------------------------------------


def test_blocking_conditions_and_reason_are_preserved():
    _, audit_service = _services()
    recommendation = _recommendation(
        recommended_action=RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
        confidence=0.0,
        reason="task is still blocked by unresolved dependencies",
        supporting_recovery_ids=(),
        blocking_conditions=("dependency 'task-0' has not completed yet",),
    )

    audit = audit_service.record("task-1", recommendation)

    assert audit.blocking_conditions == ("dependency 'task-0' has not completed yet",)
    assert audit.reason == "task is still blocked by unresolved dependencies"


# --- retrieve one decision -----------------------------------------------------------------------------------


def test_get_with_decision_id_returns_the_matching_audit():
    _, audit_service = _services()
    first = audit_service.record("task-1", _recommendation(failure_event_id="failure-1"))
    audit_service.record("task-1", _recommendation(failure_event_id="failure-2"))

    assert audit_service.get("task-1", decision_id=first.decision_id) == first


def test_get_without_decision_id_returns_the_latest_audit():
    _, audit_service = _services()
    audit_service.record("task-1", _recommendation(failure_event_id="failure-1"))
    latest = audit_service.record("task-1", _recommendation(failure_event_id="failure-2"))

    assert audit_service.get("task-1") == latest


def test_get_returns_none_for_unknown_task_or_decision():
    _, audit_service = _services()
    audit_service.record("task-1", _recommendation())

    assert audit_service.get("does-not-exist") is None
    assert audit_service.get("task-1", decision_id="does-not-exist") is None


# --- list decisions deterministically -----------------------------------------------------------------------------


def test_list_returns_audits_oldest_to_newest():
    _, audit_service = _services()
    first = audit_service.record("task-1", _recommendation(failure_event_id="failure-1"))
    second = audit_service.record("task-1", _recommendation(failure_event_id="failure-2"))
    third = audit_service.record("task-1", _recommendation(failure_event_id="failure-3"))

    audits = audit_service.list("task-1")

    assert [a.decision_id for a in audits] == [first.decision_id, second.decision_id, third.decision_id]


def test_list_limit_caps_to_most_recent_entries():
    _, audit_service = _services()
    audit_service.record("task-1", _recommendation(failure_event_id="failure-1"))
    second = audit_service.record("task-1", _recommendation(failure_event_id="failure-2"))
    third = audit_service.record("task-1", _recommendation(failure_event_id="failure-3"))

    limited = audit_service.list("task-1", limit=2)

    assert [a.decision_id for a in limited] == [second.decision_id, third.decision_id]


def test_repeated_list_is_deterministic():
    _, audit_service = _services()
    audit_service.record("task-1", _recommendation(failure_event_id="failure-1"))
    audit_service.record("task-1", _recommendation(failure_event_id="failure-2"))

    assert audit_service.list("task-1") == audit_service.list("task-1")


def test_list_rejects_negative_limit():
    _, audit_service = _services()

    with pytest.raises(InvalidAgentTaskRecoveryDecisionAuditError):
        audit_service.list("task-1", limit=-1)


def test_list_returns_empty_for_unknown_task():
    _, audit_service = _services()

    assert audit_service.list("does-not-exist") == []


# --- duplicate recording/idempotency --------------------------------------------------------------------------------


def test_duplicate_recording_returns_existing_audit():
    _, audit_service = _services()
    recommendation = _recommendation()

    first = audit_service.record("task-1", recommendation)
    second = audit_service.record("task-1", recommendation)

    assert first == second
    assert len(audit_service.list("task-1")) == 1


def test_distinct_recommendations_are_both_recorded():
    _, audit_service = _services()
    audit_service.record("task-1", _recommendation(failure_event_id="failure-1"))
    audit_service.record("task-1", _recommendation(failure_event_id="failure-2"))

    assert len(audit_service.list("task-1")) == 2


# --- multiple tasks remain isolated --------------------------------------------------------------------------------------


def test_multiple_tasks_remain_isolated():
    _, audit_service = _services()
    audit_service.record("task-1", _recommendation(task_id="task-1"))
    audit_service.record("task-2", _recommendation(task_id="task-2"))
    audit_service.record("task-2", _recommendation(task_id="task-2", failure_event_id="failure-2"))

    assert len(audit_service.list("task-1")) == 1
    assert len(audit_service.list("task-2")) == 2


# --- original recommendation remains unchanged ---------------------------------------------------------------------------


def test_recording_does_not_mutate_the_original_recommendation():
    _, audit_service = _services()
    recommendation = _recommendation()

    audit_service.record("task-1", recommendation)

    # frozen dataclass -- field values must still read exactly as constructed
    assert recommendation.task_id == "task-1"
    assert recommendation.recommended_action == RECOVERY_ACTION_REFRESH_CONTEXT
    assert recommendation.confidence == 0.75
    assert recommendation.supporting_recovery_ids == ("recovery-1", "recovery-2")
    assert recommendation.failure_event_id == "failure-event-1"


def test_recording_does_not_add_unrelated_events():
    event_service, audit_service = _services()
    from backend.agent_task_events import CONTEXT_UPDATED

    event_service.emit("task-1", CONTEXT_UPDATED)
    before_count = len(event_service.get("task-1"))

    audit_service.record("task-1", _recommendation())

    after_count = len(event_service.get("task-1"))
    assert after_count == before_count + 1  # only the new audit event was added
