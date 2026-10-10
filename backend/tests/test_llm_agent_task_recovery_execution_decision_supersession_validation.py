from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    FRESHNESS_STALE,
    REVALIDATION_REPLACED,
    SUPERSESSION_INVALID,
    SUPERSESSION_VALID,
    AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord,
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionDecisionSupersessionRecord,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore,
    InvalidAgentTaskRecoveryExecutionDecisionSupersessionValidationError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService,
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
        audit_service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(store=self.freshness_store)
        common = dict(
            decision_store=self.decision_store, freshness_audit_service=audit_service,
            chain_index_store=self.index_store,
        )
        self.supersession = LLMAgentTaskRecoveryExecutionDecisionSupersessionService(
            store=self.supersession_store, **common
        )
        self.service = LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService(
            supersession_store=self.supersession_store, supersession_service=self.supersession, **common
        )

    def decision(self, decision_id, minutes, verdict=EXECUTION_DECISION_ALLOW, task_id=TASK_ID):
        return self.decision_store.save(
            AgentTaskRecoveryExecutionPreconditionDecision(
                task_id=task_id, snapshot_id="snap", authorization_id="auth-1", decision=verdict,
                reason="test", blocking_conditions=(), warnings=(), validation_result=None,
                drift_classification=None, approval_reconciliation=None, created_at=_at(minutes),
                decision_id=decision_id,
            )
        )

    def raw(self, old, new, reason="r", old_verdict=EXECUTION_DECISION_ALLOW, new_verdict=EXECUTION_DECISION_ALLOW):
        """Write a supersession record directly, bypassing supersede()'s checks."""
        self.supersession_store.save(
            AgentTaskRecoveryExecutionDecisionSupersessionRecord(
                task_id=TASK_ID, previous_decision_id=old, replacement_decision_id=new,
                previous_decision=old_verdict, replacement_decision=new_verdict, reason=reason, recorded_at=T0,
            )
        )


def _mentions(result, text):
    return any(text in issue for issue in result.issues)


def test_valid_chain():
    f = _Fixture()
    f.decision("d1", 0, verdict=EXECUTION_DECISION_BLOCK)
    f.decision("d2", 5)
    f.decision("d3", 10)
    f.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")
    f.supersession.supersede(TASK_ID, "d2", "d3", "revalidated again")

    result = f.service.validate(TASK_ID)

    assert result.status == SUPERSESSION_VALID and result.valid and not result.invalid, result.issues
    assert result.chain == ("d1", "d2", "d3")
    assert result.terminal_decision_id == "d3"


def test_single_decision_without_supersession_is_valid():
    f = _Fixture()
    f.decision("d1", 0)

    result = f.service.validate(TASK_ID)

    assert result.valid and result.chain == ("d1",) and result.terminal_decision_id == "d1"


def test_missing_decisions_fail_closed():
    f = _Fixture()
    f.decision("d1", 0)
    f.raw("d1", "gone")

    result = f.service.validate(TASK_ID)

    assert result.status == SUPERSESSION_INVALID and result.terminal_decision_id is None
    assert _mentions(result, "replacement decision gone does not exist")


def test_cross_task_links_are_reported():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("other", 5, task_id="task-2")
    f.raw("d1", "other")

    result = f.service.validate(TASK_ID)

    assert _mentions(result, "replacement decision other belongs to task 'task-2'")


def test_cycles_are_reported():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.raw("d1", "d2")
    f.raw("d2", "d1")

    result = f.service.validate(TASK_ID)

    assert result.invalid
    assert _mentions(result, "lineage is cyclic: d1 -> d2 -> d1")


def test_conflicting_successors_are_reported():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.decision("d3", 6)
    f.raw("d1", "d2")
    f.raw("d1", "d3")

    result = f.service.validate(TASK_ID)

    assert _mentions(result, "decision d1 has conflicting successors d2 and d3")


def test_invalid_ordering_and_missing_reason_are_reported():
    f = _Fixture()
    f.decision("d1", 5)
    f.decision("d2", 0)
    f.raw("d1", "d2", reason="  ")

    result = f.service.validate(TASK_ID)

    assert _mentions(result, "the replacement is not newer")
    assert _mentions(result, "has no valid supersession reason")


def test_recorded_verdicts_must_match_persisted_decisions():
    f = _Fixture()
    f.decision("d1", 0, verdict=EXECUTION_DECISION_BLOCK)
    f.decision("d2", 5)
    f.raw("d1", "d2", old_verdict=EXECUTION_DECISION_ALLOW)

    result = f.service.validate(TASK_ID)

    assert _mentions(result, "recorded previous verdict 'allow' disagrees with the persisted decision's 'block'")


def test_mismatched_terminal_decision_is_reported():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")
    f.decision("d3", 10)  # newer, not superseding anything

    result = f.service.validate(TASK_ID)

    assert result.invalid and result.chain == ("d1", "d2")
    assert _mentions(result, "authoritative current decision is ambiguous")


def test_disagreement_with_freshness_and_reconciliation_records():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.decision("d3", 6)
    f.raw("d1", "d3")
    f.freshness_store.save(
        AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord(
            task_id=TASK_ID, decision_id="d1", freshness_status=FRESHNESS_STALE, freshness_reason="r",
            decision_state_version="v1", current_state_version="v2", revalidated=True,
            revalidation_action=REVALIDATION_REPLACED, replacement_decision_id="d2", recorded_at=_at(7),
        )
    )
    f.index_store.save(
        AgentTaskRecoveryExecutionDecisionFreshnessChainIndex(
            task_id=TASK_ID, links=(), current_decision_id="d2", updated_at=T0,
        )
    )

    result = f.service.validate(TASK_ID)

    assert _mentions(result, "supersession d1 -> d3 disagrees with freshness revalidation d1 -> d2")
    assert _mentions(result, "the reconciled current pointer d2 disagrees with the lineage terminal d3")


def test_empty_history_fails_closed():
    result = _Fixture().service.validate(TASK_ID)

    assert result.invalid and result.chain == () and result.terminal_decision_id is None
    assert _mentions(result, "no decisions are recorded")


def test_validation_is_read_only_and_deterministic():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.raw("d1", "d2")
    f.raw("d1", "d2")
    before = (f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID), f.index_store.get(TASK_ID))

    first = f.service.validate(TASK_ID)
    second = f.service.validate(TASK_ID)

    assert first == second
    assert _mentions(first, "is recorded more than once")
    assert before == (
        f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID), f.index_store.get(TASK_ID),
    )


@pytest.mark.parametrize("task_id", ["", None])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionValidationError):
        LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService().validate(task_id)
