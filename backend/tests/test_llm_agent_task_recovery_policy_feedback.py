import pytest

from backend.agent_task_event_analytics import (
    InvalidAgentTaskRecoveryPolicyFeedbackError,
    LLMAgentTaskEventFailureClassifier,
    LLMAgentTaskRecoveryDecisionAuditService,
    LLMAgentTaskRecoveryDecisionComparisonService,
    LLMAgentTaskRecoveryEffectivenessService,
    LLMAgentTaskRecoveryHistoryService,
    LLMAgentTaskRecoveryOutcomeService,
    LLMAgentTaskRecoveryPolicyFeedbackService,
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_REFRESH_CONTEXT,
    RECOVERY_POLICY_FEEDBACK_EFFECTIVE,
    RECOVERY_POLICY_FEEDBACK_INEFFECTIVE,
    RECOVERY_POLICY_FEEDBACK_UNKNOWN,
    AgentTaskFailureRecoveryResult,
    AgentTaskRecoveryDecisionComparison,
    AgentTaskRecoveryRecommendation,
)
from backend.agent_task_events import (
    InMemoryAgentTaskEventStore,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
)
from backend.agent_task_lifecycle import FAILED, PLANNED


def _stack():
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    outcome_service = LLMAgentTaskRecoveryOutcomeService(event_service=event_service, query_service=query_service)
    history_service = LLMAgentTaskRecoveryHistoryService(outcome_service=outcome_service)
    effectiveness_service = LLMAgentTaskRecoveryEffectivenessService(
        history_service=history_service, failure_classifier=classifier
    )
    audit_service = LLMAgentTaskRecoveryDecisionAuditService(event_service=event_service, query_service=query_service)
    comparison_service = LLMAgentTaskRecoveryDecisionComparisonService(
        audit_service=audit_service, history_service=history_service, effectiveness_service=effectiveness_service
    )
    feedback_service = LLMAgentTaskRecoveryPolicyFeedbackService(
        event_service=event_service, query_service=query_service
    )
    return event_service, outcome_service, audit_service, comparison_service, feedback_service


def _recommendation(task_id="task-1", **overrides):
    fields = dict(
        task_id=task_id,
        recommended_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        confidence=0.8,
        reason="context refresh has a strong track record",
        supporting_recovery_ids=(),
        blocking_conditions=(),
        failure_event_id="failure-event-1",
    )
    fields.update(overrides)
    return AgentTaskRecoveryRecommendation(**fields)


def _outcome_result(task_id="task-1", **overrides):
    fields = dict(
        task_id=task_id,
        planned_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        executed_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        success=True,
        failure_reason=None,
        affected_reference="context refreshed",
        source_failure_event_id="failure-event-1",
        partial=False,
    )
    fields.update(overrides)
    return AgentTaskFailureRecoveryResult(**fields)


def _illegal_failure(event_service, task_id="task-1"):
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _real_terminal_failure(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


# --- effective recommendation feedback --------------------------------------------------------------


def test_effective_recommendation_feedback():
    event_service, outcome_service, audit_service, comparison_service, feedback_service = _stack()
    failing = _illegal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    outcome = outcome_service.record(
        "task-1", _outcome_result(source_failure_event_id=failing.event_id, success=True)
    )
    comparison = comparison_service.compare("task-1", decision_id=audit.decision_id)

    feedback = feedback_service.record("task-1", comparison)

    assert feedback.task_id == "task-1"
    assert feedback.decision_id == audit.decision_id
    assert feedback.recovery_id == outcome.recovery_id
    assert feedback.recommended_action == RECOVERY_ACTION_REFRESH_CONTEXT
    assert feedback.executed_action == RECOVERY_ACTION_REFRESH_CONTEXT
    assert feedback.recommendation_confidence == 0.8
    assert feedback.effectiveness == RECOVERY_POLICY_FEEDBACK_EFFECTIVE
    assert feedback.feedback_reason == comparison.comparison_reason


def test_record_rejects_blank_task_id():
    _, _, _, _, feedback_service = _stack()
    comparison = AgentTaskRecoveryDecisionComparison(
        task_id="task-1",
        decision_id="d1",
        recommended_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        executed_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        recommendation_confidence=0.5,
        outcome_status="success",
        was_followed=True,
        was_effective=True,
        comparison_reason="ok",
        recovery_id="r1",
    )
    with pytest.raises(InvalidAgentTaskRecoveryPolicyFeedbackError):
        feedback_service.record("", comparison)


def test_record_rejects_wrong_type():
    _, _, _, _, feedback_service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPolicyFeedbackError):
        feedback_service.record("task-1", "not-a-comparison")


def test_record_rejects_task_id_mismatch():
    _, _, _, _, feedback_service = _stack()
    comparison = AgentTaskRecoveryDecisionComparison(
        task_id="task-2",
        decision_id="d1",
        recommended_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        executed_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        recommendation_confidence=0.5,
        outcome_status="success",
        was_followed=True,
        was_effective=True,
        comparison_reason="ok",
        recovery_id="r1",
    )
    with pytest.raises(InvalidAgentTaskRecoveryPolicyFeedbackError):
        feedback_service.record("task-1", comparison)


# --- ineffective recommendation --------------------------------------------------------------


def test_ineffective_recommendation_feedback():
    event_service, outcome_service, audit_service, comparison_service, feedback_service = _stack()
    failing = _real_terminal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    outcome_service.record(
        "task-1",
        _outcome_result(
            source_failure_event_id=failing.event_id,
            success=False,
            failure_reason="context store unavailable",
            affected_reference=None,
        ),
    )
    comparison = comparison_service.compare("task-1", decision_id=audit.decision_id)

    feedback = feedback_service.record("task-1", comparison)

    assert feedback.effectiveness == RECOVERY_POLICY_FEEDBACK_INEFFECTIVE
    assert feedback.executed_action == RECOVERY_ACTION_REFRESH_CONTEXT


# --- unknown outcome --------------------------------------------------------------


def test_unknown_outcome_when_no_corresponding_recovery():
    event_service, _, audit_service, comparison_service, feedback_service = _stack()
    failing = _illegal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    comparison = comparison_service.compare("task-1", decision_id=audit.decision_id)

    feedback = feedback_service.record("task-1", comparison)

    assert feedback.effectiveness == RECOVERY_POLICY_FEEDBACK_UNKNOWN
    assert feedback.executed_action is None
    assert feedback.recovery_id is None


def test_unknown_outcome_when_insufficient_evidence():
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    outcome_service = LLMAgentTaskRecoveryOutcomeService(event_service=event_service, query_service=query_service)
    history_service = LLMAgentTaskRecoveryHistoryService(outcome_service=outcome_service)
    effectiveness_service = LLMAgentTaskRecoveryEffectivenessService(history_service=history_service)  # no classifier
    audit_service = LLMAgentTaskRecoveryDecisionAuditService(event_service=event_service, query_service=query_service)
    comparison_service = LLMAgentTaskRecoveryDecisionComparisonService(
        audit_service=audit_service, history_service=history_service, effectiveness_service=effectiveness_service
    )
    feedback_service = LLMAgentTaskRecoveryPolicyFeedbackService(
        event_service=event_service, query_service=query_service
    )

    failing = _illegal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    outcome_service.record("task-1", _outcome_result(source_failure_event_id=failing.event_id, success=True))
    comparison = comparison_service.compare("task-1", decision_id=audit.decision_id)
    assert comparison.was_effective is None  # no classifier wired into effectiveness_service here

    feedback = feedback_service.record("task-1", comparison)

    assert feedback.effectiveness == RECOVERY_POLICY_FEEDBACK_UNKNOWN
    assert feedback.executed_action is not None


# --- recommendation vs executed-action mismatch --------------------------------------------------------------


def test_recommendation_vs_executed_action_mismatch():
    event_service, outcome_service, audit_service, comparison_service, feedback_service = _stack()
    failing = _illegal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    outcome_service.record(
        "task-1",
        _outcome_result(
            source_failure_event_id=failing.event_id,
            planned_action=RECOVERY_ACTION_MARK_UNRECOVERABLE,
            executed_action=RECOVERY_ACTION_MARK_UNRECOVERABLE,
            success=True,
            affected_reference="dead-lettered",
        ),
    )
    comparison = comparison_service.compare("task-1", decision_id=audit.decision_id)
    assert comparison.was_followed is False

    feedback = feedback_service.record("task-1", comparison)

    assert feedback.recommended_action == RECOVERY_ACTION_REFRESH_CONTEXT
    assert feedback.executed_action == RECOVERY_ACTION_MARK_UNRECOVERABLE
    assert "was not followed" in feedback.feedback_reason


# --- duplicate feedback --------------------------------------------------------------


def test_duplicate_feedback_is_idempotent():
    event_service, outcome_service, audit_service, comparison_service, feedback_service = _stack()
    failing = _real_terminal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    outcome_service.record("task-1", _outcome_result(source_failure_event_id=failing.event_id, success=True))
    comparison = comparison_service.compare("task-1", decision_id=audit.decision_id)

    first = feedback_service.record("task-1", comparison)
    second = feedback_service.record("task-1", comparison)

    assert first == second
    assert len(feedback_service.list("task-1")) == 1


def test_genuinely_distinct_feedback_both_persist():
    event_service, outcome_service, audit_service, comparison_service, feedback_service = _stack()
    first_failure = _illegal_failure(event_service)
    second_failure = event_service.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    first_audit = audit_service.record("task-1", _recommendation(failure_event_id=first_failure.event_id))
    second_audit = audit_service.record(
        "task-1", _recommendation(failure_event_id=second_failure.event_id, confidence=0.5)
    )
    outcome_service.record("task-1", _outcome_result(source_failure_event_id=first_failure.event_id, success=True))
    outcome_service.record(
        "task-1",
        _outcome_result(
            source_failure_event_id=second_failure.event_id,
            success=False,
            failure_reason="nope",
            affected_reference=None,
        ),
    )

    first_comparison = comparison_service.compare("task-1", decision_id=first_audit.decision_id)
    second_comparison = comparison_service.compare("task-1", decision_id=second_audit.decision_id)

    feedback_service.record("task-1", first_comparison)
    feedback_service.record("task-1", second_comparison)

    assert len(feedback_service.list("task-1")) == 2


# --- existing policy/strategy integration --------------------------------------------------------------


def test_publishes_through_supplied_policy_publisher_once_per_new_record():
    event_service, outcome_service, audit_service, comparison_service, _ = _stack()
    published = []
    feedback_service = LLMAgentTaskRecoveryPolicyFeedbackService(
        event_service=event_service,
        query_service=LLMAgentTaskEventQueryService(store=event_service.store),
        policy_publisher=published.append,
    )
    failing = _illegal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    outcome_service.record("task-1", _outcome_result(source_failure_event_id=failing.event_id, success=True))
    comparison = comparison_service.compare("task-1", decision_id=audit.decision_id)

    feedback = feedback_service.record("task-1", comparison)
    feedback_service.record("task-1", comparison)  # duplicate, must not re-publish

    assert len(published) == 1
    assert published[0] == feedback


def test_publisher_exception_does_not_prevent_feedback_from_being_recorded():
    event_service, outcome_service, audit_service, comparison_service, _ = _stack()

    def _broken_publisher(feedback):
        raise RuntimeError("downstream policy system unavailable")

    feedback_service = LLMAgentTaskRecoveryPolicyFeedbackService(
        event_service=event_service,
        query_service=LLMAgentTaskEventQueryService(store=event_service.store),
        policy_publisher=_broken_publisher,
    )
    failing = _illegal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    outcome_service.record("task-1", _outcome_result(source_failure_event_id=failing.event_id, success=True))
    comparison = comparison_service.compare("task-1", decision_id=audit.decision_id)

    feedback = feedback_service.record("task-1", comparison)

    assert feedback.effectiveness == RECOVERY_POLICY_FEEDBACK_EFFECTIVE
    assert feedback_service.get("task-1").feedback_id == feedback.feedback_id


# --- unrelated policy data remains unchanged --------------------------------------------------------------


def test_unrelated_task_feedback_remains_unaffected():
    event_service, outcome_service, audit_service, comparison_service, feedback_service = _stack()

    failing_1 = _real_terminal_failure(event_service, task_id="task-1")
    audit_1 = audit_service.record("task-1", _recommendation(task_id="task-1", failure_event_id=failing_1.event_id))
    outcome_service.record(
        "task-1", _outcome_result(task_id="task-1", source_failure_event_id=failing_1.event_id, success=True)
    )
    comparison_1 = comparison_service.compare("task-1", decision_id=audit_1.decision_id)
    feedback_service.record("task-1", comparison_1)

    failing_2 = _real_terminal_failure(event_service, task_id="task-2")
    audit_2 = audit_service.record("task-2", _recommendation(task_id="task-2", failure_event_id=failing_2.event_id))
    outcome_service.record(
        "task-2",
        _outcome_result(
            task_id="task-2",
            source_failure_event_id=failing_2.event_id,
            success=False,
            failure_reason="broken",
            affected_reference=None,
        ),
    )
    comparison_2 = comparison_service.compare("task-2", decision_id=audit_2.decision_id)

    before = feedback_service.get("task-1")
    feedback_service.record("task-2", comparison_2)
    after = feedback_service.get("task-1")

    assert before == after
    assert len(feedback_service.list("task-1")) == 1
    task_2_feedback = feedback_service.get("task-2")
    assert task_2_feedback.effectiveness == RECOVERY_POLICY_FEEDBACK_INEFFECTIVE


def test_recording_feedback_does_not_mutate_the_underlying_audit_or_outcome():
    event_service, outcome_service, audit_service, comparison_service, feedback_service = _stack()
    failing = _real_terminal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    outcome = outcome_service.record(
        "task-1", _outcome_result(source_failure_event_id=failing.event_id, success=True)
    )
    comparison = comparison_service.compare("task-1", decision_id=audit.decision_id)

    feedback_service.record("task-1", comparison)

    assert audit_service.get("task-1", decision_id=audit.decision_id) == audit
    assert outcome_service.get("task-1", recovery_id=outcome.recovery_id) == outcome


def test_deterministic_repeated_get_and_list():
    event_service, outcome_service, audit_service, comparison_service, feedback_service = _stack()
    failing = _real_terminal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    outcome_service.record("task-1", _outcome_result(source_failure_event_id=failing.event_id, success=True))
    comparison = comparison_service.compare("task-1", decision_id=audit.decision_id)
    feedback_service.record("task-1", comparison)

    assert feedback_service.get("task-1") == feedback_service.get("task-1")
    assert feedback_service.list("task-1") == feedback_service.list("task-1")


def test_get_and_list_empty_for_task_with_no_feedback():
    _, _, _, _, feedback_service = _stack()

    assert feedback_service.get("task-1") is None
    assert feedback_service.list("task-1") == []
