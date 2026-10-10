from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    CHAIN_INVALID,
    CHAIN_VALID,
    EXECUTION_DECISION_ALLOW,
    FRESHNESS_FRESH,
    FRESHNESS_STALE,
    FRESHNESS_UNKNOWN,
    INTEGRITY_INVALID,
    INTEGRITY_VALID,
    REVALIDATION_FAILED,
    REVALIDATION_REPLACED,
    REVALIDATION_REUSED,
    AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InvalidAgentTaskRecoveryExecutionDecisionFreshnessChainValidationError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _at(minutes):
    return T0 + timedelta(minutes=minutes)


class _Fixture:
    def __init__(self, integrity_service=None):
        self.decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self.audit_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        self.service = LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService(
            decision_store=self.decision_store,
            freshness_audit_service=LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(
                store=self.audit_store
            ),
            integrity_service=integrity_service,
        )

    def decision(self, decision_id, minutes, authorization_id="auth-1", snapshot_id="snap"):
        return self.decision_store.save(
            AgentTaskRecoveryExecutionPreconditionDecision(
                task_id=TASK_ID, snapshot_id=snapshot_id, authorization_id=authorization_id,
                decision=EXECUTION_DECISION_ALLOW, reason="test", blocking_conditions=(), warnings=(),
                validation_result=None, drift_classification=None, approval_reconciliation=None,
                created_at=_at(minutes), decision_id=decision_id,
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

    def replace(self, old_id, new_id, minutes):
        self.audit(old_id, minutes, action=REVALIDATION_REPLACED, replacement=new_id)


def _issues_mention(result, text):
    return any(text in issue for issue in result.issues)


def test_single_fresh_decision_is_a_valid_chain():
    f = _Fixture()
    f.decision("d1", 0)
    f.audit("d1", 1, status=FRESHNESS_FRESH)

    result = f.service.validate(TASK_ID)

    assert result.status == CHAIN_VALID and result.valid and not result.invalid
    assert result.issues == ()
    assert result.chain == ("d1",)
    assert result.latest_decision_id == "d1"


def test_stale_decision_replaced_by_newer_successor_is_valid():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.replace("d1", "d2", 6)

    result = f.service.validate(TASK_ID)

    assert result.valid, result.issues
    assert result.chain == ("d1", "d2")
    assert result.latest_decision_id == "d2"


def test_multiple_replacements_are_followed_to_the_terminal_decision():
    f = _Fixture()
    for index, decision_id in enumerate(("d1", "d2", "d3", "d4")):
        f.decision(decision_id, index * 10)
    f.replace("d1", "d2", 11)
    f.replace("d2", "d3", 21)
    f.replace("d3", "d4", 31)
    f.audit("d4", 32, status=FRESHNESS_FRESH, action=REVALIDATION_REUSED)

    result = f.service.validate(TASK_ID)

    assert result.valid, result.issues
    assert result.chain == ("d1", "d2", "d3", "d4")
    assert result.latest_decision_id == "d4"


def test_broken_link_to_a_missing_replacement_fails_closed():
    f = _Fixture()
    f.decision("d1", 0)
    f.replace("d1", "d-missing", 1)

    result = f.service.validate(TASK_ID)

    assert result.status == CHAIN_INVALID
    assert result.latest_decision_id is None
    assert _issues_mention(result, "replacement decision d-missing (for d1) does not exist")


def test_cycle_is_detected():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.replace("d1", "d2", 6)
    f.replace("d2", "d1", 7)

    result = f.service.validate(TASK_ID)

    assert result.invalid
    assert _issues_mention(result, "cyclic")
    assert _issues_mention(result, "not newer")


def test_duplicate_and_contradictory_links_are_detected():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.decision("d3", 6)
    f.replace("d1", "d2", 7)
    f.replace("d1", "d2", 8)
    f.replace("d1", "d3", 9)

    result = f.service.validate(TASK_ID)

    assert result.invalid
    assert _issues_mention(result, "link d1 -> d2 is recorded more than once")
    assert _issues_mention(result, "replaced by both d2 and d3")


def test_contradictory_latest_state_fails_closed():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.replace("d1", "d2", 6)
    f.decision("d3", 7)  # newest, but never linked in

    result = f.service.validate(TASK_ID)

    assert result.invalid and result.latest_decision_id is None
    assert _issues_mention(result, "the latest decision d3 is not the chain's terminal point d2")
    assert _issues_mention(result, "decision d3 is not linked into the replacement chain")


def test_stale_terminal_decision_is_not_presented_as_current():
    f = _Fixture()
    f.decision("d1", 0)
    f.audit("d1", 1, status=FRESHNESS_UNKNOWN, action=REVALIDATION_FAILED)

    result = f.service.validate(TASK_ID)

    assert result.invalid
    assert _issues_mention(result, "terminal decision d1 was last evaluated unknown")


def test_missing_audit_evidence_for_a_successor_is_reported():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)

    result = f.service.validate(TASK_ID)

    assert result.invalid
    assert result.chain == ("d1",)
    assert _issues_mention(result, "decision d2 is not linked into the replacement chain (missing audit evidence)")


def test_replacement_audit_contradicting_its_own_evidence_is_reported():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.audit("d1", 6, status=FRESHNESS_FRESH, action=REVALIDATION_REUSED, replacement="d2")
    f.audit("ghost", 7, status=FRESHNESS_FRESH)

    result = f.service.validate(TASK_ID)

    assert _issues_mention(result, "its revalidation action is 'reused'")
    assert _issues_mention(result, "even though it was evaluated fresh")
    assert _issues_mention(result, "references decision ghost, which does not exist")


def test_missing_snapshot_or_authorization_reference_is_reported():
    f = _Fixture()
    f.decision("d1", 0, authorization_id=None, snapshot_id="")

    result = f.service.validate(TASK_ID)

    assert _issues_mention(result, "has no snapshot reference")
    assert _issues_mention(result, "has no authorization reference")


def test_integrity_service_failures_invalidate_the_chain():
    integrity = SimpleNamespace(
        check=lambda task_id, decision_id: SimpleNamespace(
            status=INTEGRITY_INVALID if decision_id == "d2" else INTEGRITY_VALID, issues=("tampered",)
        )
    )
    f = _Fixture(integrity_service=integrity)
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.replace("d1", "d2", 6)

    result = f.service.validate(TASK_ID)

    assert result.invalid
    assert _issues_mention(result, "decision d2 failed its integrity check: tampered")


def test_empty_history_fails_closed():
    result = _Fixture().service.validate(TASK_ID)

    assert result.invalid
    assert result.chain == () and result.latest_decision_id is None
    assert _issues_mention(result, "no decisions are recorded")


def test_validate_is_read_only_and_preserves_history():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.replace("d1", "d2", 6)
    before = (f.decision_store.history(TASK_ID), f.audit_store.list_for_task(TASK_ID))

    f.service.validate(TASK_ID)

    assert (f.decision_store.history(TASK_ID), f.audit_store.list_for_task(TASK_ID)) == before


@pytest.mark.parametrize("task_id", ["", None, 7])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionFreshnessChainValidationError):
        LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService().validate(task_id)
