from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    CONFLICT_SEVERITY_CRITICAL,
    CONFLICT_SEVERITY_HIGH,
    CONFLICT_SEVERITY_NONE,
    EXECUTION_DECISION_ALLOW,
    POINTER_STATUS_AGREES,
    POINTER_STATUS_DISAGREES,
    POINTER_STATUS_UNSET,
    RESOLUTION_CONFLICT,
    RESOLUTION_REJECTED,
    RESOLUTION_RESOLVED,
    SUPERSESSION_CONFLICT_INVALID_REASON,
    SUPERSESSION_CONFLICT_MISSING_DECISION,
    SUPERSESSION_CONFLICT_MULTIPLE_SUCCESSORS,
    SUPERSESSION_CONFLICT_POINTER_DISAGREEMENT,
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionDecisionSupersessionRecord,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore,
    InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictReportError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictReportingService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService,
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
        self.index_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        common = dict(
            decision_store=self.decision_store, chain_index_store=self.index_store,
            freshness_audit_service=LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(
                store=InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
            ),
        )
        self.supersession = LLMAgentTaskRecoveryExecutionDecisionSupersessionService(
            store=self.supersession_store, **common
        )
        self.reconciler = LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService(**common)
        resolution = LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService(
            supersession_store=self.supersession_store, **common
        )
        self.detector = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService(
            supersession_store=self.supersession_store, resolution_service=resolution, **common
        )
        self.service = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictReportingService(
            conflict_service=self.detector, resolution_service=resolution,
        )

    def decision(self, decision_id, minutes):
        return self.decision_store.save(
            AgentTaskRecoveryExecutionPreconditionDecision(
                task_id=TASK_ID, snapshot_id="snap", authorization_id="auth-1", decision=EXECUTION_DECISION_ALLOW,
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


def _stable(report):
    return replace(report, generated_at=T0)


def test_clean_chain_reports_no_conflicts_and_agreeing_pointer():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")
    f.reconciler.reconcile(TASK_ID)

    report = f.service.report(TASK_ID)

    assert report.conflict_count == 0 and report.unresolved_conflicts == ()
    assert report.conflict_types == () and report.counts_by_type == {}
    assert report.severity == CONFLICT_SEVERITY_NONE
    assert report.pointer_status == POINTER_STATUS_AGREES and report.reconciled_pointer == "d2"
    assert report.terminal_decision_id == "d2"
    assert report.resolution_state == RESOLUTION_RESOLVED and report.chain_validation_status == "valid"


def test_single_conflict_is_reported_with_its_exact_evidence():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.raw("d1", "d2", reason="")

    report = f.service.report(TASK_ID)
    detected = f.detector.detect(TASK_ID)

    assert report.conflict_count == 1
    assert report.conflict_types == (SUPERSESSION_CONFLICT_INVALID_REASON,)
    assert report.unresolved_conflicts == detected.conflicts
    assert report.unresolved_conflicts[0].evidence_ids == ("s-d1-d2",)
    assert report.affected_decision_ids == ("d1", "d2")


def test_multiple_conflicts_keep_detector_order_and_counts():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.decision("d3", 6)
    f.raw("d1", "d2")
    f.raw("d1", "d3", reason=" ")
    f.raw("d1", "gone")

    report = f.service.report(TASK_ID)

    assert report.conflict_types == (
        SUPERSESSION_CONFLICT_MULTIPLE_SUCCESSORS, SUPERSESSION_CONFLICT_MISSING_DECISION,
        SUPERSESSION_CONFLICT_INVALID_REASON,
    )
    assert report.counts_by_type == {
        SUPERSESSION_CONFLICT_MULTIPLE_SUCCESSORS: 1, SUPERSESSION_CONFLICT_MISSING_DECISION: 1,
        SUPERSESSION_CONFLICT_INVALID_REASON: 1,
    }
    assert report.conflict_count == 3 and report.severity == CONFLICT_SEVERITY_CRITICAL
    assert report.resolution_state == RESOLUTION_REJECTED and report.chain_validation_status == "invalid"
    assert _stable(report) == _stable(f.service.report(TASK_ID))


def test_pointer_mismatch_is_reported_without_resolving_it():
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

    report = f.service.report(TASK_ID)

    assert report.pointer_status == POINTER_STATUS_DISAGREES
    assert report.resolution_state == RESOLUTION_CONFLICT and report.terminal_decision_id is None
    assert report.conflict_types == (SUPERSESSION_CONFLICT_POINTER_DISAGREEMENT,)
    assert report.severity == CONFLICT_SEVERITY_HIGH
    assert f.index_store.get(TASK_ID).current_decision_id == "d1"


def test_empty_task_returns_a_valid_report():
    report = _Fixture().service.report(TASK_ID)

    assert report.task_id == TASK_ID
    assert report.conflict_count == 0 and report.affected_decision_ids == ()
    assert report.severity == CONFLICT_SEVERITY_NONE
    assert report.pointer_status == POINTER_STATUS_UNSET
    assert report.chain_validation_status == "invalid"


def test_report_serializes_to_plain_data():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.raw("d1", "d2", reason="")

    data = f.service.report(TASK_ID).to_dict()

    assert data["conflict_types"] == [SUPERSESSION_CONFLICT_INVALID_REASON]
    assert data["unresolved_conflicts"][0]["evidence_ids"] == ["s-d1-d2"]
    assert isinstance(data["generated_at"], str)


@pytest.mark.parametrize("task_id", ["", None])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictReportError):
        LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictReportingService().report(task_id)
