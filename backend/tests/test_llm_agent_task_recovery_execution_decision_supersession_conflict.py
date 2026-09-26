from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    CONFLICT_SEVERITY_CRITICAL,
    CONFLICT_SEVERITY_HIGH,
    CONFLICT_SEVERITY_MEDIUM,
    CONFLICT_SEVERITY_NONE,
    EXECUTION_DECISION_ALLOW,
    FRESHNESS_STALE,
    RESOLUTION_RESOLVED,
    REVALIDATION_REPLACED,
    SUPERSESSION_CONFLICT_CROSS_TASK,
    SUPERSESSION_CONFLICT_CYCLE,
    SUPERSESSION_CONFLICT_FRESHNESS_DISAGREEMENT,
    SUPERSESSION_CONFLICT_INVALID_REASON,
    SUPERSESSION_CONFLICT_MISSING_DECISION,
    SUPERSESSION_CONFLICT_MULTIPLE_SUCCESSORS,
    SUPERSESSION_CONFLICT_POINTER_DISAGREEMENT,
    SUPERSESSION_CONFLICT_SUCCESSOR_NOT_NEWER,
    AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord,
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionDecisionSupersessionRecord,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore,
    InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _at(minutes):
    return T0 + timedelta(minutes=minutes)


class _Fixture:
    def __init__(self):
        self.decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self.supersession_store = InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore()
        self.freshness_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        self.index_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        common = dict(
            decision_store=self.decision_store, chain_index_store=self.index_store,
            freshness_audit_service=LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(
                store=self.freshness_store
            ),
        )
        self.supersession = LLMAgentTaskRecoveryExecutionDecisionSupersessionService(
            store=self.supersession_store, **common
        )
        self.service = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService(
            supersession_store=self.supersession_store, **common
        )

    def decision(self, decision_id, minutes, task_id=TASK_ID):
        return self.decision_store.save(
            AgentTaskRecoveryExecutionPreconditionDecision(
                task_id=task_id, snapshot_id="snap", authorization_id="auth-1", decision=EXECUTION_DECISION_ALLOW,
                reason="test", blocking_conditions=(), warnings=(), validation_result=None,
                drift_classification=None, approval_reconciliation=None, created_at=_at(minutes),
                decision_id=decision_id,
            )
        )

    def raw(self, old, new, reason="r", supersession_id=None):
        self.supersession_store.save(
            AgentTaskRecoveryExecutionDecisionSupersessionRecord(
                task_id=TASK_ID, previous_decision_id=old, replacement_decision_id=new,
                previous_decision=EXECUTION_DECISION_ALLOW, replacement_decision=EXECUTION_DECISION_ALLOW,
                reason=reason, recorded_at=T0, supersession_id=supersession_id or f"s-{old}-{new}",
            )
        )


def _types(result):
    return [conflict.conflict_type for conflict in result.conflicts]


def test_clean_chain_has_no_conflicts():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")

    result = f.service.detect(TASK_ID)

    assert result.has_conflicts is False and result.conflicts == ()
    assert result.severity == CONFLICT_SEVERITY_NONE and result.affected_decision_ids == ()
    assert result.resolution_state == RESOLUTION_RESOLVED


def test_multiple_successors_preserve_all_evidence():
    f = _Fixture()
    for index, decision_id in enumerate(("d1", "d2", "d3")):
        f.decision(decision_id, index * 5)
    f.raw("d1", "d2")
    f.raw("d1", "d3")

    result = f.service.detect(TASK_ID)

    (conflict,) = [c for c in result.conflicts if c.conflict_type == SUPERSESSION_CONFLICT_MULTIPLE_SUCCESSORS]
    assert conflict.decision_ids == ("d1", "d2", "d3")
    assert conflict.evidence_ids == ("s-d1-d2", "s-d1-d3")
    assert conflict.severity == CONFLICT_SEVERITY_CRITICAL and result.severity == CONFLICT_SEVERITY_CRITICAL


def test_cycle_is_detected():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.raw("d1", "d2")
    f.raw("d2", "d1")

    result = f.service.detect(TASK_ID)

    (cycle,) = [c for c in result.conflicts if c.conflict_type == SUPERSESSION_CONFLICT_CYCLE]
    assert cycle.decision_ids == ("d1", "d2")
    assert cycle.evidence_ids == ("s-d1-d2", "s-d2-d1")
    assert SUPERSESSION_CONFLICT_SUCCESSOR_NOT_NEWER in _types(result)


def test_cross_task_link_is_detected():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("other", 5, task_id="task-2")
    f.raw("d1", "other")

    result = f.service.detect(TASK_ID)

    (conflict,) = [c for c in result.conflicts if c.conflict_type == SUPERSESSION_CONFLICT_CROSS_TASK]
    assert conflict.decision_ids == ("other",) and "task-2" in conflict.detail


def test_missing_decision_is_detected():
    f = _Fixture()
    f.decision("d1", 0)
    f.raw("d1", "gone")

    assert SUPERSESSION_CONFLICT_MISSING_DECISION in _types(f.service.detect(TASK_ID))


def test_successor_older_than_predecessor_is_detected():
    f = _Fixture()
    f.decision("d1", 5)
    f.decision("d2", 0)
    f.raw("d1", "d2")

    result = f.service.detect(TASK_ID)

    (conflict,) = [c for c in result.conflicts if c.conflict_type == SUPERSESSION_CONFLICT_SUCCESSOR_NOT_NEWER]
    assert conflict.severity == CONFLICT_SEVERITY_HIGH and conflict.decision_ids == ("d1", "d2")


def test_invalid_reason_is_detected_at_medium_severity():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.raw("d1", "d2", reason=" ")

    result = f.service.detect(TASK_ID)

    assert _types(result) == [SUPERSESSION_CONFLICT_INVALID_REASON]
    assert result.severity == CONFLICT_SEVERITY_MEDIUM


def test_pointer_disagreement_is_detected_without_choosing():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")
    index = f.index_store.get(TASK_ID)
    f.index_store.save(
        AgentTaskRecoveryExecutionDecisionFreshnessChainIndex(
            task_id=TASK_ID, links=index.links, current_decision_id="d1", updated_at=T0,
        )
    )

    result = f.service.detect(TASK_ID)

    (conflict,) = result.conflicts
    assert conflict.conflict_type == SUPERSESSION_CONFLICT_POINTER_DISAGREEMENT
    assert conflict.decision_ids == ("d2", "d1")
    assert f.index_store.get(TASK_ID).current_decision_id == "d1"  # untouched


def test_freshness_disagreement_is_detected():
    f = _Fixture()
    for index, decision_id in enumerate(("d1", "d2", "d3")):
        f.decision(decision_id, index * 5)
    f.raw("d1", "d3")
    f.freshness_store.save(
        AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord(
            task_id=TASK_ID, decision_id="d1", freshness_status=FRESHNESS_STALE, freshness_reason="r",
            decision_state_version="v1", current_state_version="v2", revalidated=True,
            revalidation_action=REVALIDATION_REPLACED, replacement_decision_id="d2", recorded_at=_at(11),
            audit_id="a-1",
        )
    )

    result = f.service.detect(TASK_ID)

    (conflict,) = [c for c in result.conflicts if c.conflict_type == SUPERSESSION_CONFLICT_FRESHNESS_DISAGREEMENT]
    assert conflict.decision_ids == ("d1", "d3", "d2")
    assert conflict.evidence_ids == ("a-1", "s-d1-d3")


def test_multiple_simultaneous_conflicts_are_ordered_deterministically():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.decision("d3", 6)
    f.raw("d1", "d3", reason="")
    f.raw("d1", "d2")
    f.raw("d1", "gone")

    first = f.service.detect(TASK_ID)
    second = f.service.detect(TASK_ID)

    assert first == second
    assert _types(first) == [
        SUPERSESSION_CONFLICT_MULTIPLE_SUCCESSORS, SUPERSESSION_CONFLICT_MISSING_DECISION,
        SUPERSESSION_CONFLICT_INVALID_REASON,
    ]
    assert first.affected_decision_ids == ("d1", "d2", "d3", "gone")
    assert first.conflicts[0].evidence_ids == ("s-d1-d2", "s-d1-d3", "s-d1-gone")


def test_detection_is_read_only():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.raw("d1", "d2")
    f.raw("d2", "d1")
    before = (f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID), f.index_store.get(TASK_ID))

    f.service.detect(TASK_ID)
    f.service.detect(TASK_ID)

    assert before == (
        f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID), f.index_store.get(TASK_ID),
    )


@pytest.mark.parametrize("task_id", ["", None])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictError):
        LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService().detect(task_id)
