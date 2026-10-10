from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    IMPACT_LIFECYCLE_CLEAN,
    IMPACT_LIFECYCLE_REMEDIATED,
    IMPACT_LIFECYCLE_UNRESOLVED,
    RESOLUTION_REJECTED,
    build_impact_invalidation_lifecycle_service,
)
from lifecycle_support import _resolution
from test_llm_agent_task_recovery_execution_decision_impact_invalidation_lifecycle import TASK_ID, _VerifyFixture


def _build(f, **overrides):
    return build_impact_invalidation_lifecycle_service(
        resolution_service=overrides.pop("resolution_service", _resolution()),
        decision_store=f.decision_store, snapshot_service=f.snapshots,
        chain_index_store=SimpleNamespace(get=lambda task_id: f.pointer),
        precondition_revalidation_service=f.calls, preflight_invalidation_service=f.calls,
        retry_scheduler=f.calls, chain_reconciliation_service=f.calls, integrity_service=f.integrity,
        **overrides,
    )


def test_factory_wired_lifecycle_remediates_with_only_injected_boundaries():
    f = _VerifyFixture(same_snapshot=True)

    result = _build(f).run(TASK_ID)

    assert result.status == IMPACT_LIFECYCLE_REMEDIATED, (result.errors, result.verification)
    assert (result.previous_decision_id, result.authoritative_decision_id) == ("d1", "d2")
    assert result.verification.valid


def test_injected_resolution_service_is_the_only_decision_source():
    f = _VerifyFixture()

    clean = _build(f, resolution_service=_resolution(chain=("d2",))).run(TASK_ID)
    rejected = _build(f, resolution_service=_resolution(chain=(), state=RESOLUTION_REJECTED)).run(TASK_ID)

    assert clean.status == IMPACT_LIFECYCLE_CLEAN
    assert rejected.status == IMPACT_LIFECYCLE_UNRESOLVED and f.calls.log == []


def test_any_collaborator_can_be_replaced_by_a_test_double():
    f = _VerifyFixture(same_snapshot=True)
    seen = []
    double = SimpleNamespace(validate=lambda task_id, plan: seen.append(plan) or SimpleNamespace(
        valid=False, issues=("double says no",), blocking_actions=(),
    ))

    result = _build(f, plan_validation_service=double).run(TASK_ID)

    assert len(seen) == 1 and result.errors == ("double says no",) and f.calls.log == []


def test_each_call_builds_an_independent_stack():
    f = _VerifyFixture()
    assert _build(f)._audit is not _build(f)._audit


def test_unknown_collaborator_name_is_rejected():
    with pytest.raises(TypeError):
        _build(_VerifyFixture(), not_a_service=object())
