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
    InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditError,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService,
    SUPERSESSION_INVALID,
    SUPERSESSION_VALID,
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


def _run(f):
    return f.service.execute(TASK_ID, f.planner.plan(TASK_ID))


def test_all_success_is_audited_with_pre_and_post_chain_status():
    f = _Fixture()
    f.stale_pointer()
    result = _run(f)
    audit = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService()

    record = audit.record(TASK_ID, result)

    assert record.operation_id == result.operation_id
    assert [o.conflict_id for o in record.applied] == [o.conflict_id for o in result.applied]
    assert record.applied[0].decision_ids == ("d2", "d1")
    assert record.delegated == () and record.failed == () and record.still_blocking == ()
    assert record.conflict_ids == (result.applied[0].conflict_id,)
    assert record.pre_chain_status == SUPERSESSION_INVALID
    assert (record.post_chain_status, record.post_terminal_decision_id) == (SUPERSESSION_VALID, "d2")
    assert record.executed_at == result.executed_at and record.schema_version == 1


def test_partial_failure_is_audited_with_reasons():
    f = _Fixture(revalidation=_FakeRevalidation(fail_for={"e1"}))
    f.disagreement("d", 0)
    f.disagreement("e", 100)
    result = _run(f)

    record = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService().record(TASK_ID, result)

    assert len(record.delegated) == 1 and record.delegated[0].decision_ids[0] == "d1"
    (failure,) = record.failed
    assert failure.decision_ids[0] == "e1" and "snapshot service unavailable" in failure.detail
    assert set(record.still_blocking) == set(result.still_blocking)
    assert record.post_chain_status == SUPERSESSION_INVALID


def test_delegated_revalidation_is_separated_from_applied_repairs():
    f = _Fixture()
    f.disagreement()
    result = _run(f)

    record = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService().record(TASK_ID, result)

    assert record.applied == ()
    assert [o.outcome for o in record.delegated] == [CONFLICT_ACTION_DELEGATED]
    assert record.delegated[0].conflict_id in record.still_blocking


def test_manual_review_conflicts_are_audited_as_skipped_and_blocking():
    f = _Fixture()
    for index, decision_id in enumerate(("d1", "d2", "d3")):
        f.decision(decision_id, index * 5)
    f.raw("d1", "d2")
    f.raw("d1", "d3")
    result = _run(f)

    record = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService().record(TASK_ID, result)

    (skipped,) = record.skipped
    assert skipped.outcome == CONFLICT_ACTION_SKIPPED and skipped.decision_ids == ("d1", "d2", "d3")
    assert record.still_blocking == (skipped.conflict_id,)
    assert record.applied == record.delegated == record.failed == ()


def test_duplicate_recording_is_idempotent_and_history_is_append_only():
    f = _Fixture()
    f.stale_pointer()
    audit = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService()
    first_result = _run(f)
    second_result = _run(f)  # a new operation: nothing left to apply

    first = audit.record(TASK_ID, first_result)
    again = audit.record(TASK_ID, first_result)
    second = audit.record(TASK_ID, second_result)

    assert again == first
    assert second.operation_id != first.operation_id and second.applied == ()
    assert [r.audit_id for r in audit.list(TASK_ID)] == [first.audit_id, second.audit_id]
    assert audit.get(first.audit_id) == first
    assert audit.list("task-2") == []


def test_audit_never_touches_decisions_or_lineage():
    f = _Fixture()
    f.stale_pointer()
    result = _run(f)
    before = (f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID), f.index_store.get(TASK_ID))

    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService().record(TASK_ID, result)

    assert before == (
        f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID), f.index_store.get(TASK_ID),
    )


def test_invalid_arguments_are_rejected():
    f = _Fixture()
    f.stale_pointer()
    result = _run(f)
    audit = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService()

    for args in (("task-2", result), (TASK_ID, None), ("", result)):
        with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditError):
            audit.record(*args)
