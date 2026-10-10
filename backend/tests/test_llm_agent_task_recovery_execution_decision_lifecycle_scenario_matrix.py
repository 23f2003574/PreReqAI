"""Scenario matrix for the impact-invalidation lifecycle: one row per important
outcome, asserting only the externally meaningful contract (status,
authoritative decision, blockers, affected artifacts, verification, errors).
Detailed behavior stays in the per-service suites."""
from dataclasses import replace
from types import SimpleNamespace

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
    RESOLUTION_CONFLICT,
    RESOLUTION_REJECTED,
    InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleError,
)
from lifecycle_support import _lifecycle, _resolution
from test_llm_agent_task_recovery_execution_decision_impact_invalidation_lifecycle import TASK_ID, _VerifyFixture


def _clean():
    return _lifecycle(_VerifyFixture(), resolution=_resolution(chain=("d2",))).run(TASK_ID)


def _superseded_and_remediated():
    return _lifecycle(_VerifyFixture(same_snapshot=True)).run(TASK_ID)


def _review_required():
    f = _VerifyFixture(same_snapshot=True)
    real_plan = f.planner.plan

    def with_manual(task_id, staleness):
        plan = real_plan(task_id, staleness)
        manual = replace(plan.items[0], artifact_id="mystery:d1", artifact_type="mystery", action="manual_review",
                         mechanism=None, execution_blocked=True, depends_on=())
        return replace(plan, items=plan.items + (manual,))

    return _lifecycle(f, plan_service=SimpleNamespace(plan=with_manual)).run(TASK_ID)


def _blocked_by_failed_remediation():
    return _lifecycle(_VerifyFixture(fail={"invalidate"})).run(TASK_ID)


def _conflict():
    return _lifecycle(_VerifyFixture(), resolution=_resolution(chain=("d1", "d2"), state=RESOLUTION_CONFLICT)).run(TASK_ID)


def _rejected():
    return _lifecycle(_VerifyFixture(), resolution=_resolution(chain=(), state=RESOLUTION_REJECTED)).run(TASK_ID)


def _verification_failure():
    failing = SimpleNamespace(
        verify=lambda task_id, op: SimpleNamespace(mismatches=("audit disagrees",), blocking_issues=())
    )
    return _lifecycle(_VerifyFixture(same_snapshot=True), verification_service=failing).run(TASK_ID)


def _dependency_unavailable():
    def explode(task_id, plan):
        raise RuntimeError("store offline")

    return _lifecycle(_VerifyFixture(), execution_service=SimpleNamespace(execute=explode)).run(TASK_ID)


def _plan_rejected():
    rejecting = SimpleNamespace(
        validate=lambda task_id, plan: SimpleNamespace(valid=False, issues=("stale plan",), blocking_actions=("x",))
    )
    return _lifecycle(_VerifyFixture(), plan_validation_service=rejecting).run(TASK_ID)


def _already_remediated():
    lifecycle = _lifecycle(_VerifyFixture())
    lifecycle.run(TASK_ID)
    return lifecycle.run(TASK_ID)


# name: (run, status, authoritative decision, blockers, affected artifacts, verification valid, error text)
SCENARIOS = {
    "clean_allow_no_decision_change": (_clean, IMPACT_LIFECYCLE_CLEAN, "d2", (), (), None, None),
    "superseded_decision_stale_artifacts_remediated": (
        _superseded_and_remediated, IMPACT_LIFECYCLE_REMEDIATED, "d2", (),
        ("execution_snapshot:d1", "execution_pointer:d1"), True, None,
    ),
    "reconciliation_required_pointer_reconciled": (
        _superseded_and_remediated, IMPACT_LIFECYCLE_REMEDIATED, "d2", (), ("execution_pointer:d1",), True, None,
    ),
    "review_required_manual_review_item": (
        _review_required, IMPACT_LIFECYCLE_VALIDATION_FAILED, "d2", (), ("mystery:d1",), None, "mystery:d1",
    ),
    "blocked_remediation_partially_failed": (
        _blocked_by_failed_remediation, IMPACT_LIFECYCLE_BLOCKED, "d2", ("preflight:d1",), (), False, None,
    ),
    "decision_conflict_fails_closed": (_conflict, IMPACT_LIFECYCLE_UNRESOLVED, None, (), (), None, "conflict"),
    "no_authoritative_decision_rejected": (_rejected, IMPACT_LIFECYCLE_UNRESOLVED, None, (), (), None, "rejected"),
    "verification_failure_is_unsafe": (
        _verification_failure, IMPACT_LIFECYCLE_UNSAFE, "d2", (), (), False, None,
    ),
    "dependency_unavailable_execution_failed": (
        _dependency_unavailable, IMPACT_LIFECYCLE_EXECUTION_FAILED, "d2", ("execution_snapshot:d1",), (), None,
        "RuntimeError: store offline",
    ),
    "invalid_plan_stops_before_execution": (
        _plan_rejected, IMPACT_LIFECYCLE_VALIDATION_FAILED, "d2", ("x",), (), None, "stale plan",
    ),
    "stale_decision_already_remediated_is_up_to_date": (
        _already_remediated, IMPACT_LIFECYCLE_UP_TO_DATE, "d2", (), (), None, None,
    ),
}


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_lifecycle_scenario_contract(name):
    run, status, authoritative, blockers, affected, verification_valid, error_text = SCENARIOS[name]

    result = run()

    assert result.status == status, (result.status, result.errors)
    assert result.authoritative_decision_id == authoritative
    assert set(blockers) <= set(result.blocking_artifacts)
    assert set(affected) <= set(a for a in result.affected_artifacts) | {i.artifact_id for i in result.planned_actions}
    if verification_valid is None:
        assert result.verification is None or status == IMPACT_LIFECYCLE_UP_TO_DATE
    else:
        assert bool(getattr(result.verification, "valid", False)) is verification_valid
    if error_text is not None:
        assert any(error_text in error for error in result.errors)
    else:
        assert result.errors == ()


def test_configuration_invalid_blank_task_id_is_an_expected_error():
    lifecycle = _lifecycle(_VerifyFixture())
    for bad in ("", None):
        with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleError):
            lifecycle.run(bad)
