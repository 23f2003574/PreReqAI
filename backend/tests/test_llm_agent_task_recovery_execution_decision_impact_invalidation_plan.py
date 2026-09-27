import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    ARTIFACT_FRESH,
    ARTIFACT_STALE,
    ARTIFACT_UNKNOWN,
    INVALIDATION_CANCEL,
    INVALIDATION_INVALIDATE,
    INVALIDATION_MANUAL_REVIEW,
    INVALIDATION_REFRESH,
    INVALIDATION_REVALIDATE,
    AgentTaskRecoveryExecutionDecisionImpactArtifact,
    AgentTaskRecoveryExecutionDecisionImpactStalenessResult,
    InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanError,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService,
)

TASK_ID = "task-1"


def _artifact(kind, status=ARTIFACT_STALE, reference="d1", blocking=True):
    return AgentTaskRecoveryExecutionDecisionImpactArtifact(
        kind=kind, reference=reference, expected="d2", status=status, blocking=blocking,
        reason=f"{kind} is {status}",
    )


def _staleness(*artifacts):
    return AgentTaskRecoveryExecutionDecisionImpactStalenessResult(
        task_id=TASK_ID, status=ARTIFACT_STALE, artifacts=tuple(artifacts), stale_artifacts=(),
        unknown_artifacts=(), blocking_artifacts=(), revalidation_required=True, unchecked=(),
    )


def _plan(*artifacts):
    return LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService().plan(TASK_ID, _staleness(*artifacts))


@pytest.mark.parametrize(
    "kind, action, mechanism",
    [
        ("execution_snapshot", INVALIDATION_REFRESH, "PreconditionRevalidationService.revalidate"),
        ("preflight", INVALIDATION_INVALIDATE, "PreflightInvalidationService.invalidate"),
        ("authorization", INVALIDATION_REVALIDATE, "PreconditionRevalidationService.revalidate"),
        ("retry_budget", INVALIDATION_CANCEL, "LLMAgentTaskRetryScheduler.cancel_retry"),
        ("execution_pointer", INVALIDATION_REVALIDATE, "ChainReconciliationService.reconcile"),
        ("lifecycle_result", INVALIDATION_REFRESH, "SupersessionResolutionLifecycleService.resolve"),
    ],
)
def test_each_action_type_uses_an_existing_mechanism(kind, action, mechanism):
    (item,) = _plan(_artifact(kind)).items

    assert item.action == action and mechanism in item.mechanism
    assert item.artifact_id == f"{kind}:d1" and item.artifact_type == kind
    assert item.evidence_required and item.stale_reason == f"{kind} is stale"


def test_unknown_artifact_goes_to_manual_review_and_blocks():
    (item,) = _plan(_artifact("authorization", status=ARTIFACT_UNKNOWN, blocking=False)).items

    assert item.action == INVALIDATION_MANUAL_REVIEW and item.mechanism is None
    assert item.execution_blocked is True
    assert "could not be established" in item.stale_reason


def test_unsupported_artifact_type_is_never_invalidated():
    (item,) = _plan(_artifact("queued_execution")).items

    assert item.action == INVALIDATION_MANUAL_REVIEW and item.execution_blocked is True
    assert "no supported invalidation mechanism" in item.stale_reason


def test_mixed_plan_orders_dependencies_first():
    plan = _plan(
        _artifact("readiness", blocking=False), _artifact("lifecycle_result", blocking=False),
        _artifact("execution_snapshot"), _artifact("recovery_plan"), _artifact("authorization"),
        _artifact("preflight"), _artifact("retry_budget", blocking=False), _artifact("execution_pointer"),
        _artifact("mystery"),
    )

    assert [i.artifact_type for i in plan.items] == [
        "authorization", "preflight", "execution_snapshot", "recovery_plan", "retry_budget", "readiness",
        "execution_pointer", "lifecycle_result", "mystery",
    ]
    by_type = {i.artifact_type: i for i in plan.items}
    assert by_type["execution_snapshot"].depends_on == ("authorization:d1", "preflight:d1")
    assert by_type["recovery_plan"].depends_on == ("execution_snapshot:d1",)
    assert by_type["lifecycle_result"].depends_on == ("execution_pointer:d1",)
    positions = {i.artifact_id: n for n, i in enumerate(plan.items)}
    assert all(positions[dep] < positions[i.artifact_id] for i in plan.items for dep in i.depends_on)
    assert plan.counts_by_action == {
        INVALIDATION_REFRESH: 4, INVALIDATION_INVALIDATE: 1, INVALIDATION_REVALIDATE: 2,
        INVALIDATION_CANCEL: 1, INVALIDATION_MANUAL_REVIEW: 1,
    }
    assert plan.execution_blocked is True


def test_dependencies_only_reference_planned_items():
    (item,) = _plan(_artifact("execution_snapshot")).items

    assert item.depends_on == ()


def test_missing_evidence_across_artifacts_is_all_manual_review():
    plan = _plan(*(_artifact(kind, status=ARTIFACT_UNKNOWN) for kind in ("authorization", "recovery_plan")))

    assert [i.action for i in plan.items] == [INVALIDATION_MANUAL_REVIEW] * 2
    assert all(i.execution_blocked for i in plan.items)


def test_empty_and_fresh_only_staleness_produce_an_empty_plan():
    assert _plan().items == ()
    plan = _plan(_artifact("authorization", status=ARTIFACT_FRESH))
    assert plan.items == () and plan.execution_blocked is False


def test_no_stale_artifact_is_discarded_and_output_is_deterministic():
    artifacts = [_artifact("readiness", blocking=False), _artifact("mystery"), _artifact("preflight")]
    first, second = _plan(*artifacts), _plan(*artifacts)

    assert first == second
    assert {i.artifact_type for i in first.items} == {"readiness", "mystery", "preflight"}
    assert first.items[[i.artifact_type for i in first.items].index("readiness")].execution_blocked is False


def test_invalid_arguments_are_rejected():
    service = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService()
    for args in (("", _staleness()), (TASK_ID, None)):
        with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanError):
            service.plan(*args)
    other = AgentTaskRecoveryExecutionDecisionImpactStalenessResult(
        task_id="task-2", status=ARTIFACT_FRESH, artifacts=(), stale_artifacts=(), unknown_artifacts=(),
        blocking_artifacts=(), revalidation_required=False, unchecked=(),
    )
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanError):
        service.plan(TASK_ID, other)
