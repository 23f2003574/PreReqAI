"""Smoke test: the lifecycle facade built by the production wiring factory, over
the real resolution/supersession/chain-index/decision stores, runs end to end.
Only the remediation mechanisms and the snapshot source (genuinely external to
this package) are test doubles."""
import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    IMPACT_LIFECYCLE_BLOCKED,
    IMPACT_LIFECYCLE_CLEAN,
    IMPACT_LIFECYCLE_EXECUTION_FAILED,
    IMPACT_LIFECYCLE_REMEDIATED,
    IMPACT_LIFECYCLE_UNRESOLVED,
    IMPACT_LIFECYCLE_UNSAFE,
    IMPACT_LIFECYCLE_UP_TO_DATE,
    IMPACT_LIFECYCLE_VALIDATION_FAILED,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore,
    InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionService,
    build_impact_invalidation_lifecycle_service,
)
from test_llm_agent_task_recovery_execution_decision_impact_invalidation_lifecycle import TASK_ID, _VerifyFixture

LIFECYCLE_STATUSES = {
    IMPACT_LIFECYCLE_BLOCKED, IMPACT_LIFECYCLE_CLEAN, IMPACT_LIFECYCLE_EXECUTION_FAILED, IMPACT_LIFECYCLE_REMEDIATED,
    IMPACT_LIFECYCLE_UNRESOLVED, IMPACT_LIFECYCLE_UNSAFE, IMPACT_LIFECYCLE_UP_TO_DATE,
    IMPACT_LIFECYCLE_VALIDATION_FAILED,
}

FACADE_DEPENDENCIES = {
    "_resolution": "resolution_service",
    "_impact": "impact_service",
    "_staleness": "staleness_service",
    "_planner": "plan_service",
    "_validation": "plan_validation_service",
    "_execution": "execution_service",
    "_audit": "audit_service",
    "_verification": "verification_service",
}


def _wired(f=None):
    """Real resolution stack over f's decision store (d1 superseded by d2)."""
    f = f or _VerifyFixture(same_snapshot=True)
    index_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
    supersession_store = InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore()
    common = dict(
        decision_store=f.decision_store, chain_index_store=index_store,
        freshness_audit_service=LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(
            store=InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        ),
    )
    LLMAgentTaskRecoveryExecutionDecisionSupersessionService(store=supersession_store, **common).supersede(
        TASK_ID, "d1", "d2", "revalidated"
    )
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService(**common).reconcile(TASK_ID)
    resolution = LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService(
        supersession_store=supersession_store, **common
    )
    facade = build_impact_invalidation_lifecycle_service(
        resolution_service=resolution, decision_store=f.decision_store, snapshot_service=f.snapshots,
        chain_index_store=index_store, precondition_revalidation_service=f.calls,
        preflight_invalidation_service=f.calls, retry_scheduler=f.calls,
        chain_reconciliation_service=f.calls, integrity_service=f.integrity,
    )
    return f, facade


def test_facade_is_constructed_with_every_dependency_resolved():
    _, facade = _wired()

    assert isinstance(facade, LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleService)
    missing = [name for name in FACADE_DEPENDENCIES if getattr(facade, name, None) is None]
    assert not missing, f"lifecycle facade is missing dependencies: {missing}"


def test_facade_evaluates_a_minimal_task_and_returns_the_result_contract():
    _, facade = _wired()

    result = facade.run(TASK_ID)

    assert result.status in LIFECYCLE_STATUSES, f"unexpected lifecycle status {result.status!r}"
    assert (result.previous_decision_id, result.authoritative_decision_id) == ("d1", "d2"), result.errors
    for field in ("affected_artifacts", "planned_actions", "applied", "failed", "blocking_artifacts", "errors"):
        assert isinstance(getattr(result, field), tuple), f"{field} must be a tuple"
    assert result.task_id == TASK_ID and result.lifecycle_id


def test_facade_builds_no_dependency_of_its_own():
    doubles = {name: object() for name in FACADE_DEPENDENCIES.values()}
    f = _VerifyFixture()

    facade = build_impact_invalidation_lifecycle_service(
        resolution_service=doubles["resolution_service"], decision_store=f.decision_store,
        snapshot_service=f.snapshots, chain_index_store=None,
        **{k: v for k, v in doubles.items() if k != "resolution_service"},
    )

    for attribute, parameter in FACADE_DEPENDENCIES.items():
        assert getattr(facade, attribute) is doubles[parameter], f"{parameter} was replaced inside the facade"


def test_blocked_and_invalid_input_still_propagate():
    f = _VerifyFixture(fail={"invalidate"})
    _, facade = _wired(f)

    assert facade.run(TASK_ID).status == IMPACT_LIFECYCLE_BLOCKED
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleError):
        facade.run("")
