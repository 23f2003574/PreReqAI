from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    FRESHNESS_FRESH,
    FRESHNESS_STALE,
    REVALIDATION_REPLACED,
    AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InvalidAgentTaskRecoveryExecutionDecisionSupersessionError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService,
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
        self.freshness_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        self.index_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        self.audit_service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(store=self.freshness_store)
        self.service = LLMAgentTaskRecoveryExecutionDecisionSupersessionService(
            decision_store=self.decision_store, freshness_audit_service=self.audit_service,
            chain_index_store=self.index_store,
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

    def audit_link(self, old, new, minutes):
        self.freshness_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord(
                task_id=TASK_ID, decision_id=old, freshness_status=FRESHNESS_STALE, freshness_reason="r",
                decision_state_version="v1", current_state_version="v2", revalidated=True,
                revalidation_action=REVALIDATION_REPLACED, replacement_decision_id=new, recorded_at=_at(minutes),
            )
        )


def test_normal_supersession_records_lineage_without_touching_decisions():
    f = _Fixture()
    f.decision("d1", 0, verdict=EXECUTION_DECISION_BLOCK)
    f.decision("d2", 5, verdict=EXECUTION_DECISION_REVIEW)
    before = f.decision_store.history(TASK_ID)

    record = f.service.supersede(TASK_ID, "d1", "d2", "freshness revalidation")

    assert (record.previous_decision_id, record.replacement_decision_id) == ("d1", "d2")
    assert (record.previous_decision, record.replacement_decision) == (
        EXECUTION_DECISION_BLOCK, EXECUTION_DECISION_REVIEW,
    )
    assert record.reason == "freshness revalidation"
    assert f.service.get_current(TASK_ID) == "d2"
    assert f.decision_store.history(TASK_ID) == before
    assert f.decision_store.get("d1").decision == EXECUTION_DECISION_BLOCK


def test_duplicate_calls_are_idempotent():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)

    first = f.service.supersede(TASK_ID, "d1", "d2", "reason")
    second = f.service.supersede(TASK_ID, "d1", "d2", "a different reason")

    assert second == first
    assert len(f.service.get_supersession_chain(TASK_ID)) == 1
    assert f.index_store.get(TASK_ID).links == (("d1", "d2"),)


@pytest.mark.parametrize(
    "args, message",
    [
        (("", "d1", "d2", "r"), "task_id is required"),
        ((TASK_ID, "d1", "", "r"), "replacement_decision_id is required"),
        ((TASK_ID, "d1", "d2", ""), "reason is required"),
        ((TASK_ID, "d1", "d1", "r"), "cannot supersede itself"),
        ((TASK_ID, "d1", "missing", "r"), "replacement decision missing does not exist"),
        ((TASK_ID, "missing", "d2", "r"), "previous decision missing does not exist"),
        ((TASK_ID, "d2", "d1", "r"), "is not newer than"),
    ],
)
def test_invalid_ids_are_rejected(args, message):
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)

    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionError, match=message):
        f.service.supersede(*args)
    assert f.service.get_supersession_chain(TASK_ID) == []


def test_cross_task_ids_are_rejected():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("other", 5, task_id="task-2")

    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionError, match="belongs to task 'task-2'"):
        f.service.supersede(TASK_ID, "d1", "other", "r")


def test_cycles_are_detected_including_freshness_links():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d3", 5)
    f.audit_link("d3", "d1", 6)  # a bogus backwards link in the freshness trail

    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionError, match="would create a cycle"):
        f.service.supersede(TASK_ID, "d1", "d3", "r")


def test_conflicting_successors_are_detected():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.decision("d3", 6)
    f.service.supersede(TASK_ID, "d1", "d2", "r")

    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionError, match="already superseded by d2"):
        f.service.supersede(TASK_ID, "d1", "d3", "r")
    f.decision("d0", -1)
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionError, match="d2 already supersedes d1"):
        f.service.supersede(TASK_ID, "d0", "d2", "r")


def test_freshness_replacement_counts_as_the_same_linkage():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.decision("d3", 6)
    f.audit_link("d1", "d2", 7)

    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionError, match="already superseded by d2"):
        f.service.supersede(TASK_ID, "d1", "d3", "r")
    record = f.service.supersede(TASK_ID, "d1", "d2", "confirm revalidation")
    assert record.replacement_decision_id == "d2"
    assert f.index_store.get(TASK_ID) is None  # the audit trail already carries the link


def test_supersession_integrates_with_validation_and_reconciliation():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5, verdict=EXECUTION_DECISION_REVIEW)
    f.service.supersede(TASK_ID, "d1", "d2", "revalidated")

    validation = LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService(
        decision_store=f.decision_store, freshness_audit_service=f.audit_service, chain_index_store=f.index_store,
    ).validate(TASK_ID)
    reconciliation = LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService(
        decision_store=f.decision_store, freshness_audit_service=f.audit_service, chain_index_store=f.index_store,
    ).reconcile(TASK_ID)

    assert validation.valid and validation.chain == ("d1", "d2")
    assert reconciliation.current_decision_id == "d2"
    assert reconciliation.current_decision_state == EXECUTION_DECISION_REVIEW


def test_chain_retrieval_and_current_are_read_only():
    f = _Fixture()
    for index, decision_id in enumerate(("d1", "d2", "d3")):
        f.decision(decision_id, index * 5)
    f.service.supersede(TASK_ID, "d2", "d3", "second")
    f.service.supersede(TASK_ID, "d1", "d2", "first")
    index_before = f.index_store.get(TASK_ID)

    chain = f.service.get_supersession_chain(TASK_ID)

    assert [(r.previous_decision_id, r.replacement_decision_id) for r in chain] == [("d1", "d2"), ("d2", "d3")]
    assert f.service.get_current(TASK_ID) == "d3"
    assert f.service.get_supersession_chain(TASK_ID) == chain
    assert f.index_store.get(TASK_ID) == index_before


def test_current_fails_closed_when_ambiguous_or_empty():
    f = _Fixture()
    assert f.service.get_current(TASK_ID) is None
    assert f.service.get_supersession_chain(TASK_ID) == []

    f.decision("d1", 0)
    assert f.service.get_current(TASK_ID) == "d1"
    f.decision("d2", 5)  # newer, but not linked
    assert f.service.get_current(TASK_ID) is None
