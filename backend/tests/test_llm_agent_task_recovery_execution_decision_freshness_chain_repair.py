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
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InvalidAgentTaskRecoveryExecutionDecisionFreshnessChainRepairError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainRepairService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService,
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
        self.index_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        audit_service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(store=self.audit_store)
        self.service = LLMAgentTaskRecoveryExecutionDecisionFreshnessChainRepairService(
            decision_store=self.decision_store, freshness_audit_service=audit_service,
            chain_index_store=self.index_store,
        )
        self.validator = LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService(
            decision_store=self.decision_store, freshness_audit_service=audit_service,
            chain_index_store=self.index_store,
        )

    def decision(self, decision_id, minutes, verdict=EXECUTION_DECISION_ALLOW):
        return self.decision_store.save(
            AgentTaskRecoveryExecutionPreconditionDecision(
                task_id=TASK_ID, snapshot_id="snap", authorization_id="auth-1", decision=verdict,
                reason="test", blocking_conditions=(), warnings=(), validation_result=None,
                drift_classification=None, approval_reconciliation=None, created_at=_at(minutes),
                decision_id=decision_id,
            )
        )

    def audit(self, decision_id, minutes, status=FRESHNESS_STALE, action=None, replacement=None):
        return self.audit_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord(
                task_id=TASK_ID, decision_id=decision_id, freshness_status=status, freshness_reason="r",
                decision_state_version="v1", current_state_version="v2", revalidated=action is not None,
                revalidation_action=action, replacement_decision_id=replacement, recorded_at=_at(minutes),
            )
        )

    def snapshot(self):
        return (
            self.decision_store.history(TASK_ID), self.audit_store.list_for_task(TASK_ID),
        )


def test_missing_linkage_between_existing_decisions_is_repaired():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.audit("d1", 6, action=REVALIDATION_REPLACED)  # replacement id lost
    history_before = f.snapshot()

    result = f.service.repair(TASK_ID)

    assert result.initial_validation.invalid
    assert "linked d1 -> d2 from audit" in result.repaired[0]
    assert result.final_validation.valid, result.unresolved
    assert result.valid and result.unresolved == ()
    assert result.final_validation.chain == ("d1", "d2")
    assert f.index_store.get(TASK_ID).current_decision_id == "d2"
    assert f.snapshot() == history_before  # history untouched
    assert f.validator.validate(TASK_ID).valid


def test_unrepairable_missing_records_stay_unresolved():
    f = _Fixture()
    f.decision("d1", 0)
    f.audit("d1", 1, action=REVALIDATION_REPLACED, replacement="d-missing")
    f.audit("d-ghost", 2, action=REVALIDATION_REPLACED)

    result = f.service.repair(TASK_ID)

    assert result.final_validation.invalid
    assert any("d-missing" in issue for issue in result.unresolved)
    assert any("missing decision d-ghost" in issue for issue in result.unresolved)
    assert [d.decision_id for d in f.decision_store.history(TASK_ID)] == ["d1"]
    assert len(f.audit_store.list_for_task(TASK_ID)) == 2
    assert f.index_store.get(TASK_ID).current_decision_id is None


def test_ambiguous_linkage_is_not_inferred():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.decision("d3", 6)
    f.audit("d1", 7, action=REVALIDATION_REPLACED)

    result = f.service.repair(TASK_ID)

    assert result.final_validation.invalid
    assert any("2 existing decisions could be it" in issue for issue in result.unresolved)
    assert f.index_store.get(TASK_ID).links == ()


def test_contradictory_decisions_are_not_repaired():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.decision("d3", 6)
    f.audit("d1", 7, action=REVALIDATION_REPLACED, replacement="d2")
    f.audit("d1", 8, action=REVALIDATION_REPLACED, replacement="d3")

    result = f.service.repair(TASK_ID)

    assert result.final_validation.invalid
    assert any("replaced by both d2 and d3" in issue for issue in result.unresolved)


def test_block_is_never_silently_converted_to_allow():
    f = _Fixture()
    f.decision("d1", 0, verdict=EXECUTION_DECISION_BLOCK)
    f.decision("d2", 5, verdict=EXECUTION_DECISION_ALLOW)
    f.audit("d1", 6, action=REVALIDATION_REPLACED)

    result = f.service.repair(TASK_ID)

    assert result.final_validation.invalid
    assert any("silently turn a block decision into allow" in issue for issue in result.unresolved)
    assert f.decision_store.get("d1").decision == EXECUTION_DECISION_BLOCK


def test_review_to_review_linkage_is_repairable():
    f = _Fixture()
    f.decision("d1", 0, verdict=EXECUTION_DECISION_REVIEW)
    f.decision("d2", 5, verdict=EXECUTION_DECISION_REVIEW)
    f.audit("d1", 6, action=REVALIDATION_REPLACED)

    assert f.service.repair(TASK_ID).valid


def test_duplicate_and_stale_derived_metadata_is_cleaned_up():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.audit("d1", 6, action=REVALIDATION_REPLACED, replacement="d2")
    f.index_store.save(
        AgentTaskRecoveryExecutionDecisionFreshnessChainIndex(
            task_id=TASK_ID, links=(("d1", "d2"), ("d1", "d2"), ("d2", "gone")),
            current_decision_id="d1", updated_at=T0,
        )
    )

    result = f.service.repair(TASK_ID)

    assert result.valid, result.unresolved
    assert any("already recorded by the audit trail" in item for item in result.repaired)
    assert any("duplicate derived link d1 -> d2" in item for item in result.repaired)
    assert any("references a missing decision" in item for item in result.repaired)
    assert any("pointer from d1 to d2" in item for item in result.repaired)
    index = f.index_store.get(TASK_ID)
    assert index.links == () and index.current_decision_id == "d2"


def test_repeated_repair_is_idempotent():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.audit("d1", 6, action=REVALIDATION_REPLACED)

    first = f.service.repair(TASK_ID)
    index_after_first = f.index_store.get(TASK_ID)
    second = f.service.repair(TASK_ID)

    assert first.repaired and second.repaired == ()
    assert second.initial_validation.valid and second.final_validation.valid
    assert f.index_store.get(TASK_ID) == index_after_first


def test_already_valid_chain_needs_only_its_pointer_recorded():
    f = _Fixture()
    f.decision("d1", 0)
    f.audit("d1", 1, status=FRESHNESS_FRESH)

    result = f.service.repair(TASK_ID)

    assert result.initial_validation.valid and result.final_validation.valid
    assert result.repaired == ("updated current decision pointer from None to d1",)
    assert f.service.repair(TASK_ID).repaired == ()


@pytest.mark.parametrize("task_id", ["", None])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionFreshnessChainRepairError):
        LLMAgentTaskRecoveryExecutionDecisionFreshnessChainRepairService().repair(task_id)
