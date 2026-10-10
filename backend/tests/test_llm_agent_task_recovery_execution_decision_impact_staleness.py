from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    ARTIFACT_FRESH,
    ARTIFACT_STALE,
    ARTIFACT_UNKNOWN,
    CHANGE_IMPACT_RESTRICTED,
    CHANGE_IMPACT_UNCHANGED,
    CHANGE_IMPACT_UNKNOWN,
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    AgentTaskRecoveryExecutionDecisionChangeImpactResult,
    InvalidAgentTaskRecoveryExecutionDecisionImpactStalenessError,
    LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService,
)

TASK_ID = "task-1"


def _impact(changed=(), impact=CHANGE_IMPACT_UNCHANGED, missing=(), requires_revalidation=False):
    return AgentTaskRecoveryExecutionDecisionChangeImpactResult(
        task_id=TASK_ID, previous_decision_id="d1", current_decision_id="d2",
        previous_decision=EXECUTION_DECISION_ALLOW, current_decision=EXECUTION_DECISION_ALLOW,
        changed_areas=tuple(changed), stale_artifacts=(), blocking_conditions=(),
        requires_revalidation=requires_revalidation, execution_impact=impact, transition=None,
        missing_evidence=tuple(missing),
    )


def _service(pointer="d2", reconciled="d2", terminal="d2"):
    index = SimpleNamespace(get=lambda task_id: SimpleNamespace(current_decision_id=pointer))
    reconciliation = SimpleNamespace(
        latest=lambda task_id: SimpleNamespace(result_id="r-1", authoritative_decision_id=reconciled)
    )
    lifecycle = SimpleNamespace(latest=lambda task_id: SimpleNamespace(result_id="l-1", terminal_decision_id=terminal))
    return LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService(
        chain_index_store=index, reconciliation_result_service=reconciliation, lifecycle_result_service=lifecycle,
    )


def _by_kind(result):
    return {artifact.kind: artifact for artifact in result.artifacts}


def test_no_stale_artifacts_is_fresh():
    result = _service().check(TASK_ID, _impact())

    assert result.status == ARTIFACT_FRESH and result.fresh and not result.stale and not result.unknown
    assert result.stale_artifacts == () and result.blocking_artifacts == ()
    assert result.revalidation_required is False and result.unchecked == ()


@pytest.mark.parametrize(
    "area, kind, blocking",
    [
        ("precondition_snapshot", "execution_snapshot", True),
        ("authorization", "authorization", True),
        ("preflight", "preflight", True),
        ("recovery_plan", "recovery_plan", True),
        ("retry_budget", "retry_budget", False),
        ("readiness", "readiness", False),
    ],
)
def test_each_snapshot_backed_reference_type(area, kind, blocking):
    result = _service().check(TASK_ID, _impact(changed=(area,), impact=CHANGE_IMPACT_RESTRICTED))

    (stale,) = result.stale_artifacts
    assert (stale.kind, stale.reference, stale.expected) == (kind, "d1", "d2")
    assert stale.blocking is blocking and result.revalidation_required is True


@pytest.mark.parametrize(
    "kwargs, kind, reference",
    [
        ({"pointer": "d1"}, "execution_pointer", "d1"),
        ({"reconciled": "d0"}, "reconciliation_result", "d0"),
        ({"terminal": "d1"}, "lifecycle_result", "d1"),
    ],
)
def test_each_decision_version_mismatch(kwargs, kind, reference):
    result = _service(**kwargs).check(TASK_ID, _impact())

    (stale,) = result.stale_artifacts
    assert (stale.kind, stale.reference, stale.expected) == (kind, reference, "d2")
    assert "not the authoritative decision d2" in stale.reason


def test_multiple_stale_artifacts_are_all_reported_in_order():
    result = _service(pointer="d1", terminal="d1").check(
        TASK_ID, _impact(changed=("precondition_snapshot", "authorization", "recovery_plan"))
    )

    assert [a.kind for a in result.stale_artifacts] == [
        "execution_snapshot", "authorization", "recovery_plan", "execution_pointer", "lifecycle_result",
    ]
    assert result.status == ARTIFACT_STALE
    assert [a.kind for a in result.blocking_artifacts] == [
        "execution_snapshot", "authorization", "recovery_plan", "execution_pointer",
    ]


def test_missing_version_evidence_is_unknown_and_blocking():
    impact = _impact(impact=CHANGE_IMPACT_UNKNOWN, missing=("current decision gone is not recorded",))

    result = _service(reconciled=None).check(TASK_ID, impact)

    assert result.status == ARTIFACT_UNKNOWN and not result.fresh
    kinds = _by_kind(result)
    assert kinds["authorization"].status == ARTIFACT_UNKNOWN and kinds["authorization"].blocking
    assert kinds["reconciliation_result"].status == ARTIFACT_UNKNOWN
    assert all(a.blocking for a in result.unknown_artifacts)
    assert result.revalidation_required is True


def test_unchanged_decision_versions_stay_fresh():
    result = _service().check(TASK_ID, _impact(requires_revalidation=False))

    assert all(a.status == ARTIFACT_FRESH for a in result.artifacts)
    assert _by_kind(result)["execution_pointer"].reference == "d2"


def test_unconfigured_persistence_is_listed_not_guessed():
    result = LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService().check(TASK_ID, _impact())

    assert result.unchecked == ("execution_pointer", "reconciliation_result", "lifecycle_result")
    assert {a.kind for a in result.artifacts} == {
        "execution_snapshot", "authorization", "preflight", "recovery_plan", "retry_budget", "readiness",
    }


def test_impact_requiring_revalidation_is_propagated_and_output_is_deterministic():
    service = _service()
    impact = _impact(requires_revalidation=True)

    first, second = service.check(TASK_ID, impact), service.check(TASK_ID, impact)

    assert first == second and first.revalidation_required is True and first.fresh


def test_invalid_arguments_are_rejected():
    service = _service()
    for args in (("", _impact()), (TASK_ID, None), ("task-2", _impact())):
        with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactStalenessError):
            service.check(*args)
