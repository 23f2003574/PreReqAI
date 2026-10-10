from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    CONFLICT_ACTION_APPLIED,
    CONFLICT_ACTION_DELEGATED,
    CONFLICT_ACTION_FAILED,
    CONFLICT_ACTION_SKIPPED,
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    FRESHNESS_STALE,
    PLAN_REPAIRABLE_METADATA,
    PLAN_REQUIRES_REVALIDATION,
    REVALIDATION_REPLACED,
    AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord,
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionDecisionSupersessionRecord,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore,
    InvalidAgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationError,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _at(minutes):
    return T0 + timedelta(minutes=minutes)


class _FakeRevalidation:
    def __init__(self, fail_for=()):
        self.calls = []
        self.fail_for = set(fail_for)

    def revalidate(self, task_id, decision_id):
        self.calls.append(decision_id)
        if decision_id in self.fail_for:
            raise RuntimeError("snapshot service unavailable")
        return SimpleNamespace(action="reused", new_decision_id=None)


class _Fixture:
    def __init__(self, revalidation=None):
        self.decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self.supersession_store = InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore()
        self.freshness_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        self.index_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        audit_service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(store=self.freshness_store)
        common = dict(
            decision_store=self.decision_store, chain_index_store=self.index_store,
            freshness_audit_service=audit_service,
        )
        self.supersession = LLMAgentTaskRecoveryExecutionDecisionSupersessionService(
            store=self.supersession_store, **common
        )
        resolution = LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService(
            supersession_store=self.supersession_store, **common
        )
        detector = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService(
            supersession_store=self.supersession_store, resolution_service=resolution, **common
        )
        self.planner = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService(
            conflict_service=detector, resolution_service=resolution,
        )
        self.revalidation = revalidation or _FakeRevalidation()
        self.service = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionService(
            plan_service=self.planner,
            plan_validation_service=LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationService(
                plan_service=self.planner, decision_store=self.decision_store,
                supersession_store=self.supersession_store, freshness_audit_service=audit_service,
            ),
            reconciliation_service=LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService(**common),
            revalidation_service=self.revalidation,
            supersession_validation_service=LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService(
                supersession_store=self.supersession_store, **common
            ),
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

    def raw(self, old, new, reason="r"):
        self.supersession_store.save(
            AgentTaskRecoveryExecutionDecisionSupersessionRecord(
                task_id=TASK_ID, previous_decision_id=old, replacement_decision_id=new,
                previous_decision=EXECUTION_DECISION_ALLOW, replacement_decision=EXECUTION_DECISION_ALLOW,
                reason=reason, recorded_at=T0, supersession_id=f"s-{old}-{new}",
            )
        )

    def audit_link(self, old, new, minutes):
        self.freshness_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord(
                task_id=TASK_ID, decision_id=old, freshness_status=FRESHNESS_STALE, freshness_reason="r",
                decision_state_version="v1", current_state_version="v2", revalidated=True,
                revalidation_action=REVALIDATION_REPLACED, replacement_decision_id=new, recorded_at=_at(minutes),
                audit_id=f"a-{old}",
            )
        )

    def stale_pointer(self):
        self.decision("d1", 0, verdict=EXECUTION_DECISION_REVIEW)
        self.decision("d2", 5, verdict=EXECUTION_DECISION_BLOCK)
        self.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")
        self.index_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessChainIndex(
                task_id=TASK_ID, links=self.index_store.get(TASK_ID).links, current_decision_id="d1", updated_at=T0,
            )
        )
        return self.planner.plan(TASK_ID)

    def disagreement(self, prefix="d", start=0):
        a, b, c = (f"{prefix}{i}" for i in (1, 2, 3))
        for offset, decision_id in enumerate((a, b, c)):
            self.decision(decision_id, start + offset * 5)
        self.raw(a, c)
        self.audit_link(a, b, start + 11)


class _VerifyFixture(_Fixture):
    def __init__(self, revalidation=None):
        super().__init__(revalidation=revalidation)
        common = dict(
            decision_store=self.decision_store, chain_index_store=self.index_store,
            freshness_audit_service=LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(
                store=self.freshness_store
            ),
        )
        self.audit = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService()
        self.verifier = LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationService(
            audit_service=self.audit, decision_store=self.decision_store,
            supersession_validation_service=LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService(
                supersession_store=self.supersession_store, **common
            ),
            resolution_service=LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService(
                supersession_store=self.supersession_store, **common
            ),
            plan_service=self.planner,
        )

    def allow_pointer(self):
        self.decision("d1", 0)
        self.decision("d2", 5)
        self.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")
        self.index_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessChainIndex(
                task_id=TASK_ID, links=self.index_store.get(TASK_ID).links, current_decision_id="d1", updated_at=T0,
            )
        )

    def run_and_audit(self):
        result = self.service.execute(TASK_ID, self.planner.plan(TASK_ID))
        return result, self.audit.record(TASK_ID, result)


def _mentions(items, text):
    return any(text in item for item in items)


def test_successful_resolution_verifies():
    f = _VerifyFixture()
    f.allow_pointer()
    result, _ = f.run_and_audit()

    verification = f.verifier.verify(TASK_ID, result.operation_id)

    assert verification.valid and not verification.invalid, (verification.mismatches, verification.blocking_issues)
    assert verification.applied_actions_verified == (result.applied[0].conflict_id,)
    assert verification.remaining_conflicts == () and verification.terminal_decision_id == "d2"


def test_preserved_block_condition_keeps_execution_gated():
    f = _VerifyFixture()
    f.stale_pointer()  # d1 review -> d2 block
    result, _ = f.run_and_audit()

    verification = f.verifier.verify(TASK_ID, result.operation_id)

    assert verification.mismatches == ()
    assert verification.terminal_decision_id == "d2"
    assert _mentions(verification.blocking_issues, "terminal decision d2 is 'block'")
    assert verification.invalid


def test_partial_resolution_reports_remaining_blockers():
    f = _VerifyFixture(revalidation=_FakeRevalidation(fail_for={"e1"}))
    f.disagreement("d", 0)
    f.disagreement("e", 100)
    result, _ = f.run_and_audit()

    verification = f.verifier.verify(TASK_ID, result.operation_id)

    assert verification.mismatches == ()
    assert set(verification.remaining_conflicts) == set(result.still_blocking)
    assert _mentions(verification.blocking_issues, "still blocks execution")
    assert _mentions(verification.blocking_issues, "the lineage does not resolve")
    assert verification.terminal_decision_id is None


def test_invalid_linkage_introduced_after_the_operation_is_a_mismatch():
    f = _VerifyFixture()
    f.allow_pointer()
    result, _ = f.run_and_audit()
    f.decision("d3", 10)
    f.raw("d1", "d3")  # a competing successor appears later

    verification = f.verifier.verify(TASK_ID, result.operation_id)

    assert _mentions(verification.mismatches, "multiple_successors conflict")
    assert _mentions(verification.mismatches, "introduced after the operation")
    assert verification.terminal_decision_id is None


def test_audit_mismatch_is_reported():
    f = _VerifyFixture()
    f.allow_pointer()
    result = f.service.execute(TASK_ID, f.planner.plan(TASK_ID))
    forged = replace(result, applied=(), final_validation=result.initial_validation)
    f.audit.record(TASK_ID, forged)

    verification = f.verifier.verify(TASK_ID, result.operation_id)

    assert _mentions(verification.mismatches, "audit recorded chain status 'invalid', but it is now 'valid'")
    assert _mentions(verification.mismatches, "audit recorded terminal decision None")


def test_forbidden_applied_action_is_a_mismatch():
    f = _VerifyFixture()
    for index, decision_id in enumerate(("d1", "d2", "d3")):
        f.decision(decision_id, index * 5)
    f.raw("d1", "d2")
    f.raw("d1", "d3")
    result = f.service.execute(TASK_ID, f.planner.plan(TASK_ID))
    f.audit.record(TASK_ID, replace(result, applied=tuple(replace(o, outcome="applied") for o in result.skipped)))

    verification = f.verifier.verify(TASK_ID, result.operation_id)

    assert _mentions(verification.mismatches, "which a validated plan never lets execution apply")


def test_missing_operation_fails_closed():
    verification = _VerifyFixture().verifier.verify(TASK_ID, "no-such-operation")

    assert verification.invalid and verification.terminal_decision_id is None
    assert _mentions(verification.blocking_issues, "has no audit record")


def test_repeated_verification_is_deterministic_and_read_only():
    f = _VerifyFixture()
    f.allow_pointer()
    result, _ = f.run_and_audit()
    before = (f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID), f.index_store.get(TASK_ID))

    first = f.verifier.verify(TASK_ID, result.operation_id)
    second = f.verifier.verify(TASK_ID, result.operation_id)

    assert first == second
    assert before == (
        f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID), f.index_store.get(TASK_ID),
    )


@pytest.mark.parametrize("args", [("", "op"), (TASK_ID, ""), (None, "op")])
def test_invalid_arguments_are_rejected(args):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationError):
        LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationService().verify(*args)
