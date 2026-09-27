from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    FRESHNESS_STALE,
    REVALIDATION_REPLACED,
    SUPERSESSION_LIFECYCLE_BLOCKED,
    SUPERSESSION_LIFECYCLE_CLEAN,
    SUPERSESSION_LIFECYCLE_EXECUTION_FAILED,
    SUPERSESSION_LIFECYCLE_RESOLVED,
    SUPERSESSION_LIFECYCLE_UNSAFE,
    SUPERSESSION_LIFECYCLE_VALIDATION_FAILED,
    AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord,
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionDecisionSupersessionRecord,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore,
    InvalidAgentTaskRecoveryExecutionDecisionSupersessionLifecycleVerificationError,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleResultService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleVerificationService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _at(minutes):
    return T0 + timedelta(minutes=minutes)


class _FakeRevalidation:
    def __init__(self, fail_for=()):
        self.calls, self.fail_for = [], set(fail_for)

    def revalidate(self, task_id, decision_id):
        self.calls.append(decision_id)
        if decision_id in self.fail_for:
            raise RuntimeError("snapshot service unavailable")
        return SimpleNamespace(action="reused", new_decision_id=None)


class _Fixture:
    def __init__(self, revalidation=None, **overrides):
        self.decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self.supersession_store = InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore()
        self.freshness_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        self.index_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        self.audit_store = InMemoryAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditStore()
        audit_service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(store=self.freshness_store)
        self.supersession = LLMAgentTaskRecoveryExecutionDecisionSupersessionService(
            decision_store=self.decision_store, store=self.supersession_store,
            freshness_audit_service=audit_service, chain_index_store=self.index_store,
        )
        self.revalidation = revalidation or _FakeRevalidation()
        self.service = LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleService(
            decision_store=self.decision_store, supersession_store=self.supersession_store,
            freshness_audit_service=audit_service, chain_index_store=self.index_store,
            revalidation_service=self.revalidation,
            audit_service=LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService(
                store=self.audit_store
            ),
            **overrides,
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

    def raw(self, old, new):
        self.supersession_store.save(
            AgentTaskRecoveryExecutionDecisionSupersessionRecord(
                task_id=TASK_ID, previous_decision_id=old, replacement_decision_id=new,
                previous_decision=EXECUTION_DECISION_ALLOW, replacement_decision=EXECUTION_DECISION_ALLOW,
                reason="r", recorded_at=T0, supersession_id=f"s-{old}-{new}",
            )
        )

    def stale_pointer(self, first=EXECUTION_DECISION_ALLOW, second=EXECUTION_DECISION_ALLOW):
        self.decision("d1", 0, verdict=first)
        self.decision("d2", 5, verdict=second)
        self.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")
        self.index_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessChainIndex(
                task_id=TASK_ID, links=self.index_store.get(TASK_ID).links, current_decision_id="d1", updated_at=T0,
            )
        )

    def disagreement(self, prefix="d", start=0):
        a, b, c = (f"{prefix}{i}" for i in (1, 2, 3))
        for offset, decision_id in enumerate((a, b, c)):
            self.decision(decision_id, start + offset * 5)
        self.raw(a, c)
        self.freshness_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord(
                task_id=TASK_ID, decision_id=a, freshness_status=FRESHNESS_STALE, freshness_reason="r",
                decision_state_version="v1", current_state_version="v2", revalidated=True,
                revalidation_action=REVALIDATION_REPLACED, replacement_decision_id=b, recorded_at=_at(start + 11),
                audit_id=f"a-{a}",
            )
        )


class _VerifyFixture(_Fixture):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        lifecycle = self.service
        self.results = LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleResultService()
        self.verifier = LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleVerificationService(
            lifecycle_result_service=self.results, audit_service=lifecycle._audit_service,
            resolution_verification_service=lifecycle._verification_service,
            resolution_service=lifecycle._resolution_service, plan_service=lifecycle._plan_service,
        )

    def run(self):
        record = self.results.record(TASK_ID, self.service.resolve(TASK_ID))
        return record, self.verifier.verify(TASK_ID, record.result_id)


def _mentions(items, text):
    return any(text in item for item in items)


def test_fully_successful_lifecycle_verifies():
    f = _VerifyFixture()
    f.stale_pointer()

    record, result = f.run()

    assert record.state == SUPERSESSION_LIFECYCLE_RESOLVED
    assert result.valid and not result.invalid, (result.mismatches, result.missing_evidence)
    assert result.remaining_blockers == () and result.terminal_decision_id == "d2"


def test_partial_resolution_is_truthfully_recorded():
    f = _VerifyFixture(revalidation=_FakeRevalidation(fail_for={"e1"}))
    f.disagreement("d", 0)
    f.disagreement("e", 100)

    record, result = f.run()

    assert record.partial is True
    assert result.valid, (result.mismatches, result.missing_evidence)
    assert result.remaining_blockers and result.terminal_decision_id is None


def test_unresolved_manual_review_blockers_remain():
    f = _VerifyFixture()
    for index, decision_id in enumerate(("d1", "d2", "d3")):
        f.decision(decision_id, index * 5)
    f.raw("d1", "d2")
    f.raw("d1", "d3")

    record, result = f.run()

    assert record.state == SUPERSESSION_LIFECYCLE_BLOCKED
    assert result.valid and _mentions(result.remaining_blockers, "still blocks execution")


def test_stale_lifecycle_result_is_detected():
    f = _VerifyFixture()
    f.stale_pointer()
    record, _ = f.run()
    f.decision("d3", 10)
    f.supersession.supersede(TASK_ID, "d2", "d3", "revalidated later")

    result = f.verifier.verify(TASK_ID, record.result_id)

    assert result.invalid
    assert _mentions(result.mismatches, "recorded terminal decision d2 is no longer authoritative")


def test_audit_mismatch_is_detected():
    f = _VerifyFixture()
    f.stale_pointer()
    lifecycle = f.service.resolve(TASK_ID)
    forged = f.results.record(TASK_ID, replace(lifecycle, audit_id="some-other-audit", applied=()))

    result = f.verifier.verify(TASK_ID, forged.result_id)

    assert _mentions(result.mismatches, "references audit some-other-audit")
    assert _mentions(result.mismatches, "applied actions disagree with the audit record")


def test_incorrect_success_status_is_detected():
    f = _VerifyFixture()
    for index, decision_id in enumerate(("d1", "d2", "d3")):
        f.decision(decision_id, index * 5)
    f.raw("d1", "d2")
    f.raw("d1", "d3")
    lifecycle = f.service.resolve(TASK_ID)
    forged = f.results.record(TASK_ID, replace(lifecycle, state=SUPERSESSION_LIFECYCLE_RESOLVED, terminal_decision_id="d3"))

    result = f.verifier.verify(TASK_ID, forged.result_id)

    assert _mentions(result.mismatches, "recorded as resolved without a passing verification")
    assert _mentions(result.mismatches, "recorded terminal decision d3 is no longer authoritative")
    assert result.terminal_decision_id is None


def test_missing_evidence_is_reported():
    f = _VerifyFixture()
    f.stale_pointer()
    lifecycle = f.service.resolve(TASK_ID)
    orphan = f.results.record(TASK_ID, replace(lifecycle, operation_id="unknown-operation"))

    result = f.verifier.verify(TASK_ID, orphan.result_id)
    unknown = f.verifier.verify(TASK_ID, "no-such-result")

    assert _mentions(result.missing_evidence, "no audit record exists for operation unknown-operation")
    assert result.invalid and result.terminal_decision_id is None
    assert unknown.invalid and _mentions(unknown.missing_evidence, "does not exist for task")


def test_clean_lifecycle_verifies_and_detects_new_conflicts():
    f = _VerifyFixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")
    record, result = f.run()
    assert record.state == SUPERSESSION_LIFECYCLE_CLEAN and result.valid

    f.decision("d3", 6)
    f.raw("d1", "d3")
    later = f.verifier.verify(TASK_ID, record.result_id)

    assert _mentions(later.mismatches, "recorded clean, but conflicts now exist")


def test_repeated_verification_is_deterministic_and_read_only():
    f = _VerifyFixture()
    f.stale_pointer()
    record, first = f.run()
    before = (
        f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID),
        f.index_store.get(TASK_ID), f.results.history(TASK_ID), f.audit_store.list_for_task(TASK_ID),
    )

    second = f.verifier.verify(TASK_ID, record.result_id)

    assert first == second
    assert before == (
        f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID),
        f.index_store.get(TASK_ID), f.results.history(TASK_ID), f.audit_store.list_for_task(TASK_ID),
    )


@pytest.mark.parametrize("args", [("", "r"), (TASK_ID, ""), (None, "r")])
def test_invalid_arguments_are_rejected(args):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionLifecycleVerificationError):
        LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleVerificationService().verify(*args)
