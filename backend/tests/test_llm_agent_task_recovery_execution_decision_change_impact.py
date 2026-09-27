from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    CHANGE_IMPACT_ENABLED,
    CHANGE_IMPACT_RELAXED,
    CHANGE_IMPACT_RESTRICTED,
    CHANGE_IMPACT_STILL_BLOCKED,
    CHANGE_IMPACT_UNCHANGED,
    CHANGE_IMPACT_UNKNOWN,
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    AgentTaskRecoveryExecutionPreconditionDecision,
    AgentTaskRecoveryExecutionPreconditionSnapshot,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore,
    InvalidAgentTaskRecoveryExecutionDecisionChangeImpactError,
    LLMAgentTaskRecoveryExecutionDecisionChangeImpactService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _at(minutes):
    return T0 + timedelta(minutes=minutes)


class _Snapshots:
    """Stands in for the snapshot service -- only get() is used."""

    def __init__(self):
        self.by_id = {}

    def add(self, snapshot_id, **overrides):
        fields = dict(
            task_id=TASK_ID, authorization_id="auth-1", preflight_id="pre-1", approval_id="appr-1",
            authorization_status="active", task_state="failed", recovery_plan="plan-a",
            retry_eligibility="eligible", readiness="ready", captured_at=T0, snapshot_id=snapshot_id,
        )
        fields.update(overrides)
        self.by_id[snapshot_id] = AgentTaskRecoveryExecutionPreconditionSnapshot(**fields)

    def get(self, task_id, snapshot_id):
        snapshot = self.by_id.get(snapshot_id)
        return snapshot if snapshot is not None and snapshot.task_id == task_id else None


class _Fixture:
    def __init__(self, with_snapshots=True):
        self.decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self.snapshots = _Snapshots() if with_snapshots else None
        self.service = LLMAgentTaskRecoveryExecutionDecisionChangeImpactService(
            decision_store=self.decision_store, snapshot_service=self.snapshots,
        )

    def decision(self, decision_id, minutes, verdict, snapshot_id="snap-1", blocking=()):
        return self.decision_store.save(
            AgentTaskRecoveryExecutionPreconditionDecision(
                task_id=TASK_ID, snapshot_id=snapshot_id, authorization_id="auth-1", decision=verdict,
                reason="test", blocking_conditions=blocking, warnings=(), validation_result=None,
                drift_classification=None, approval_reconciliation=None, created_at=_at(minutes),
                decision_id=decision_id,
            )
        )


def test_allow_to_allow_on_the_same_snapshot_is_unchanged():
    f = _Fixture()
    f.snapshots.add("snap-1")
    f.decision("d1", 0, EXECUTION_DECISION_ALLOW)
    f.decision("d2", 5, EXECUTION_DECISION_ALLOW)

    result = f.service.analyze(TASK_ID, "d1", "d2")

    assert result.execution_impact == CHANGE_IMPACT_UNCHANGED
    assert result.changed_areas == () and result.stale_artifacts == () and result.blocking_conditions == ()
    assert result.requires_revalidation is False
    assert result.transition.transition_type == "allow_to_allow"


def test_allow_to_review_restricts_and_marks_snapshot_areas():
    f = _Fixture()
    f.snapshots.add("snap-1")
    f.snapshots.add("snap-2", authorization_id="auth-2", recovery_plan="plan-b", retry_eligibility="exhausted")
    f.decision("d1", 0, EXECUTION_DECISION_ALLOW)
    f.decision("d2", 5, EXECUTION_DECISION_REVIEW, snapshot_id="snap-2", blocking=("approval pending",))

    result = f.service.analyze(TASK_ID, "d1", "d2")

    assert result.execution_impact == CHANGE_IMPACT_RESTRICTED
    assert result.changed_areas == (
        "decision_state", "blocking_conditions", "precondition_snapshot", "authorization", "recovery_plan",
        "retry_budget",
    )
    assert "authorization auth-1" in result.stale_artifacts
    assert "precondition snapshot snap-1" in result.stale_artifacts
    assert result.blocking_conditions == ("approval pending", "current decision d2 is review")
    assert result.requires_revalidation is True


def test_allow_to_block_restricts():
    f = _Fixture()
    f.snapshots.add("snap-1")
    f.decision("d1", 0, EXECUTION_DECISION_ALLOW)
    f.decision("d2", 5, EXECUTION_DECISION_BLOCK, blocking=("authorization revoked",))

    result = f.service.analyze(TASK_ID, "d1", "d2")

    assert result.execution_impact == CHANGE_IMPACT_RESTRICTED
    assert result.transition.requires_attention is True
    assert "current decision d2 is block" in result.blocking_conditions


def test_review_to_allow_enables_but_flags_stale_eligibility():
    f = _Fixture()
    f.snapshots.add("snap-1")
    f.decision("d1", 0, EXECUTION_DECISION_REVIEW)
    f.decision("d2", 5, EXECUTION_DECISION_ALLOW)

    result = f.service.analyze(TASK_ID, "d1", "d2")

    assert result.execution_impact == CHANGE_IMPACT_ENABLED
    assert result.stale_artifacts == ("execution eligibility derived from review decision d1",)
    assert result.blocking_conditions == () and result.requires_revalidation is False


def test_block_to_review_relaxes_but_still_requires_revalidation():
    f = _Fixture()
    f.snapshots.add("snap-1")
    f.decision("d1", 0, EXECUTION_DECISION_BLOCK)
    f.decision("d2", 5, EXECUTION_DECISION_REVIEW)

    result = f.service.analyze(TASK_ID, "d1", "d2")

    assert result.execution_impact == CHANGE_IMPACT_RELAXED
    assert result.requires_revalidation is True


def test_unchanged_block_state_stays_blocked():
    f = _Fixture()
    f.snapshots.add("snap-1")
    f.decision("d1", 0, EXECUTION_DECISION_BLOCK)

    result = f.service.analyze(TASK_ID, "d1", "d1")

    assert result.execution_impact == CHANGE_IMPACT_STILL_BLOCKED
    assert result.changed_areas == () and result.transition is None


def test_missing_decision_references_fail_closed():
    f = _Fixture()
    f.decision("d1", 0, EXECUTION_DECISION_ALLOW)

    result = f.service.analyze(TASK_ID, "d1", "gone")

    assert result.execution_impact == CHANGE_IMPACT_UNKNOWN
    assert result.requires_revalidation is True and result.changed_areas == ()
    assert result.missing_evidence == ("current decision gone is not recorded for task task-1",)


def test_missing_snapshot_evidence_is_not_guessed():
    f = _Fixture(with_snapshots=False)
    f.decision("d1", 0, EXECUTION_DECISION_ALLOW, snapshot_id="snap-1")
    f.decision("d2", 5, EXECUTION_DECISION_ALLOW, snapshot_id="snap-2")

    result = f.service.analyze(TASK_ID, "d1", "d2")

    assert result.changed_areas == ("precondition_snapshot",)
    assert len(result.missing_evidence) == 2 and result.requires_revalidation is True


def test_non_authoritative_current_decision_is_blocking():
    f = _Fixture()
    f.snapshots.add("snap-1")
    f.decision("d1", 0, EXECUTION_DECISION_ALLOW)
    f.decision("d2", 5, EXECUTION_DECISION_ALLOW)
    common = dict(
        decision_store=f.decision_store, chain_index_store=InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore(),
        freshness_audit_service=LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(
            store=InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        ),
    )
    store = InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore()
    LLMAgentTaskRecoveryExecutionDecisionSupersessionService(store=store, **common).supersede(TASK_ID, "d1", "d2", "r")
    service = LLMAgentTaskRecoveryExecutionDecisionChangeImpactService(
        decision_store=f.decision_store, snapshot_service=f.snapshots,
        supersession_resolution_service=LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService(
            supersession_store=store, **common
        ),
    )

    assert service.analyze(TASK_ID, "d1", "d2").blocking_conditions == ()
    backwards = service.analyze(TASK_ID, "d2", "d1")
    assert "decision d1 is not the authoritative terminal d2" in backwards.blocking_conditions
    assert backwards.requires_revalidation is True


def test_analysis_is_deterministic_and_read_only():
    f = _Fixture()
    f.snapshots.add("snap-1")
    f.decision("d1", 0, EXECUTION_DECISION_ALLOW)
    f.decision("d2", 5, EXECUTION_DECISION_BLOCK)
    before = f.decision_store.history(TASK_ID)

    assert f.service.analyze(TASK_ID, "d1", "d2").changed_areas == f.service.analyze(TASK_ID, "d1", "d2").changed_areas
    assert f.decision_store.history(TASK_ID) == before


@pytest.mark.parametrize("args", [("", "d1", "d2"), (TASK_ID, "", "d2"), (TASK_ID, "d1", None)])
def test_invalid_arguments_are_rejected(args):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionChangeImpactError):
        LLMAgentTaskRecoveryExecutionDecisionChangeImpactService().analyze(*args)
