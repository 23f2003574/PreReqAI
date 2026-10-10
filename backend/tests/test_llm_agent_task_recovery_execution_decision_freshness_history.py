from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    FRESHNESS_FRESH,
    FRESHNESS_HISTORY_DECISION_RECORDED,
    FRESHNESS_HISTORY_FRESH_REUSE,
    FRESHNESS_HISTORY_INDETERMINATE_DETECTED,
    FRESHNESS_HISTORY_REVALIDATION_FAILED,
    FRESHNESS_HISTORY_REVALIDATION_REPLACED,
    FRESHNESS_HISTORY_REVALIDATION_REUSED,
    FRESHNESS_HISTORY_STALE_DETECTED,
    FRESHNESS_STALE,
    FRESHNESS_UNKNOWN,
    REVALIDATION_FAILED,
    REVALIDATION_REPLACED,
    REVALIDATION_REUSED,
    AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InvalidAgentTaskRecoveryExecutionDecisionFreshnessHistoryError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessHistoryService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _at(minutes):
    return T0 + timedelta(minutes=minutes)


class _Fixture:
    def __init__(self):
        self.decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self.audit_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        self.service = LLMAgentTaskRecoveryExecutionDecisionFreshnessHistoryService(
            decision_store=self.decision_store,
            freshness_audit_service=LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(
                store=self.audit_store
            ),
        )

    def decision(self, decision_id, minutes, verdict=EXECUTION_DECISION_ALLOW, task_id=TASK_ID):
        return self.decision_store.save(
            AgentTaskRecoveryExecutionPreconditionDecision(
                task_id=task_id, snapshot_id=f"snap-{decision_id}", authorization_id="auth-1",
                decision=verdict, reason="test", blocking_conditions=(), warnings=(),
                validation_result=None, drift_classification=None, approval_reconciliation=None,
                created_at=_at(minutes), decision_id=decision_id,
            )
        )

    def audit(self, decision_id, minutes, status, action=None, replacement=None, audit_id=None):
        return self.audit_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord(
                task_id=TASK_ID, decision_id=decision_id, freshness_status=status,
                freshness_reason=f"{status} reason", decision_state_version="v1",
                current_state_version="v1" if status == FRESHNESS_FRESH else "v2",
                revalidated=action is not None, revalidation_action=action,
                replacement_decision_id=replacement, recorded_at=_at(minutes),
                **({"audit_id": audit_id} if audit_id else {}),
            )
        )


def test_fresh_decision_is_reuse_not_revalidation():
    f = _Fixture()
    f.decision("d1", 0)
    f.audit("d1", 1, FRESHNESS_FRESH)
    f.audit("d1", 2, FRESHNESS_FRESH, action=REVALIDATION_REUSED)

    history = f.service.get_history(TASK_ID)

    assert [e.event_type for e in history.events] == [
        FRESHNESS_HISTORY_DECISION_RECORDED, FRESHNESS_HISTORY_FRESH_REUSE,
        FRESHNESS_HISTORY_REVALIDATION_REUSED,
    ]
    assert history.events[1].revalidated is False
    assert history.events[2].revalidated is True
    assert history.fresh_reuse_count == 1
    assert history.revalidation_count == 1
    assert history.replacement_count == 0
    assert history.original_decision_id == history.current_decision_id == "d1"
    assert history.complete is True


def test_stale_to_replacement_links_old_to_new():
    f = _Fixture()
    f.decision("d1", 0)
    f.audit("d1", 5, FRESHNESS_STALE)
    f.decision("d2", 6, verdict=EXECUTION_DECISION_BLOCK)
    f.audit("d1", 7, FRESHNESS_STALE, action=REVALIDATION_REPLACED, replacement="d2", audit_id="a-rep")

    history = f.service.get_history(TASK_ID)

    assert [e.event_type for e in history.events] == [
        FRESHNESS_HISTORY_DECISION_RECORDED, FRESHNESS_HISTORY_STALE_DETECTED,
        FRESHNESS_HISTORY_DECISION_RECORDED, FRESHNESS_HISTORY_REVALIDATION_REPLACED,
    ]
    assert history.events[2].execution_decision == EXECUTION_DECISION_BLOCK
    assert history.events[1].freshness_reason == "stale reason"
    assert history.events[1].current_state_version == "v2"
    (link,) = history.links
    assert (link.old_decision_id, link.new_decision_id, link.audit_id) == ("d1", "d2", "a-rep")
    assert link.linked_at == _at(7) and link.replacement_found is True
    assert history.current_decision_id == "d2"
    assert history.complete is True


def test_failed_revalidation_keeps_old_decision_current():
    f = _Fixture()
    f.decision("d1", 0)
    f.audit("d1", 3, FRESHNESS_UNKNOWN, action=REVALIDATION_FAILED)

    history = f.service.get_history(TASK_ID)

    assert history.events[-1].event_type == FRESHNESS_HISTORY_REVALIDATION_FAILED
    assert history.events[-1].freshness_status == FRESHNESS_UNKNOWN
    assert history.failed_revalidation_count == 1
    assert history.links == ()
    assert history.current_decision_id == "d1"
    assert history.complete is True


def test_multiple_replacements_form_one_chain():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 10)
    f.audit("d1", 11, FRESHNESS_STALE, action=REVALIDATION_REPLACED, replacement="d2")
    f.decision("d3", 20)
    f.audit("d2", 21, FRESHNESS_UNKNOWN, action=REVALIDATION_REPLACED, replacement="d3")

    history = f.service.get_history(TASK_ID)

    assert [(l.old_decision_id, l.new_decision_id) for l in history.links] == [("d1", "d2"), ("d2", "d3")]
    assert history.replacement_count == 2
    assert history.revalidation_count == 2
    assert history.original_decision_id == "d1"
    assert history.current_decision_id == "d3"


def test_incomplete_history_is_reported_not_invented():
    f = _Fixture()
    f.decision("d1", 0)
    f.audit("d1", 1, FRESHNESS_STALE, action=REVALIDATION_REPLACED, replacement="d-missing")
    f.audit("d-ghost", 2, FRESHNESS_FRESH)
    f.audit("d1", 3, FRESHNESS_UNKNOWN)

    history = f.service.get_history(TASK_ID)

    assert history.complete is False
    assert history.links[0].replacement_found is False
    assert history.current_decision_id == "d-missing"
    assert history.events[-1].event_type == FRESHNESS_HISTORY_INDETERMINATE_DETECTED
    assert len(history.gaps) == 3
    assert any("d-missing" in gap for gap in history.gaps)
    assert any("d-ghost" in gap for gap in history.gaps)
    assert any("no revalidation was recorded" in gap for gap in history.gaps)
    # Only persisted records appear -- nothing is synthesized for the gaps.
    assert [e.decision_id for e in history.events if e.event_type == FRESHNESS_HISTORY_DECISION_RECORDED] == ["d1"]


def test_stale_followed_by_revalidation_is_not_a_gap():
    f = _Fixture()
    f.decision("d1", 0)
    f.audit("d1", 1, FRESHNESS_STALE)
    f.audit("d1", 2, FRESHNESS_STALE, action=REVALIDATION_FAILED)

    assert f.service.get_history(TASK_ID).gaps == ()


def test_ordering_is_chronological_and_deterministic_on_ties():
    f = _Fixture()
    f.audit("d2", 5, FRESHNESS_FRESH, audit_id="a-late")
    f.decision("d2", 5)
    f.decision("d1", 0)
    f.audit("d1", 5, FRESHNESS_FRESH, audit_id="a-tie")

    first = f.service.get_history(TASK_ID)
    second = f.service.get_history(TASK_ID)

    assert [(e.event_type, e.decision_id) for e in first.events] == [
        (FRESHNESS_HISTORY_DECISION_RECORDED, "d1"),
        (FRESHNESS_HISTORY_DECISION_RECORDED, "d2"),
        (FRESHNESS_HISTORY_FRESH_REUSE, "d2"),
        (FRESHNESS_HISTORY_FRESH_REUSE, "d1"),
    ]
    assert [e.sequence for e in first.events] == [1, 2, 3, 4]
    assert first.events == second.events


def test_empty_task_and_other_tasks_are_isolated():
    f = _Fixture()
    f.decision("other", 0, task_id="task-2")

    history = f.service.get_history(TASK_ID)

    assert history.events == () and history.links == ()
    assert history.original_decision_id is None and history.current_decision_id is None
    assert history.complete is True


def test_get_history_is_read_only():
    f = _Fixture()
    f.decision("d1", 0)
    f.audit("d1", 1, FRESHNESS_STALE)
    before = (f.decision_store.history(TASK_ID), f.audit_store.list_for_task(TASK_ID))

    f.service.get_history(TASK_ID)

    assert (f.decision_store.history(TASK_ID), f.audit_store.list_for_task(TASK_ID)) == before


@pytest.mark.parametrize("task_id", ["", None, 3])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionFreshnessHistoryError):
        LLMAgentTaskRecoveryExecutionDecisionFreshnessHistoryService().get_history(task_id)
