from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    FINALIZATION_CHECK_FAILED,
    FINALIZATION_CHECK_WARNING,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleFinalizationError,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationService,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleFinalizationService,
)
from lifecycle_support import _lifecycle, _resolution
from test_llm_agent_task_recovery_execution_decision_impact_invalidation_lifecycle import TASK_ID, _VerifyFixture


def _service(persist=True, facade_mutator=None, resolution=None, surfaces=None, verification=None, fixture=None):
    f = fixture or _VerifyFixture(same_snapshot=True)
    own_resolution = _resolution()
    facade = _lifecycle(f, resolution=own_resolution)
    results = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultService()
    if persist:
        results.record(TASK_ID, facade.run(TASK_ID))
    verifier = verification or LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationService(
        lifecycle_result_service=results, audit_service=f.audit, verification_service=f.verifier,
        resolution_service=own_resolution,
    )
    if facade_mutator:
        facade_mutator(facade)
    service = LLMAgentTaskRecoveryExecutionDecisionLifecycleFinalizationService(
        facade, resolution or own_resolution, results, verifier,
        expected_surfaces={"api": lambda: None} if surfaces is None else surfaces,
    )
    return f, facade, service


def _failed(result):
    return [c.name for c in result.checks if c.status == FINALIZATION_CHECK_FAILED]


def test_ready_when_every_required_check_passes():
    _, _, service = _service()

    result = service.finalize(TASK_ID)

    assert result.ready and result.blocking_issues == () and result.warnings == ()
    assert [c.name for c in result.checks] == [
        "configuration", "dependencies", "wiring", "decision_lineage", "critical_blockers",
        "persisted_results", "timeout_safety", "surfaces",
    ]


def test_missing_configuration_blocks_and_names_the_dependency():
    _, _, service = _service(facade_mutator=lambda facade: setattr(facade, "_audit", None))

    result = service.finalize(TASK_ID)

    assert not result.ready and "configuration" in _failed(result)
    assert any("audit_service" in issue for issue in result.blocking_issues)


def test_unresolvable_dependency_blocks():
    _, _, service = _service(facade_mutator=lambda facade: setattr(facade, "_planner", object()))

    result = service.finalize(TASK_ID)

    assert not result.ready and "dependencies" in _failed(result)
    assert any("plan_service.plan" in issue for issue in result.blocking_issues)


def test_invalid_lineage_blocks():
    rejected = SimpleNamespace(resolve=lambda task_id: SimpleNamespace(resolution_state="rejected"))
    _, _, service = _service(resolution=rejected)

    result = service.finalize(TASK_ID)

    assert not result.ready and "decision_lineage" in _failed(result)
    assert "wiring" in _failed(result)  # a different resolution service than the facade's


def test_verification_failure_of_a_persisted_result_blocks():
    broken = SimpleNamespace(verify=lambda task_id, result_id: SimpleNamespace(status="invalid"))
    _, _, service = _service(verification=broken)

    result = service.finalize(TASK_ID)

    assert not result.ready and _failed(result) == ["persisted_results"]


def test_timeout_safety_failure_blocks():
    class LeakyFacade:
        def __init__(self, **kwargs):
            pass

        def run(self, task_id):
            raise TimeoutError("leaked")

    _, facade, _ = _service()
    facade_type = type(facade)

    def leak(f):
        f.__class__ = LeakyFacade

    _, _, service = _service(facade_mutator=leak)
    result = service.finalize(TASK_ID)

    assert not result.ready and "timeout_safety" in _failed(result)
    assert facade_type is not LeakyFacade


def test_multiple_blockers_are_all_reported_in_fixed_order():
    _, _, service = _service(facade_mutator=lambda facade: setattr(facade, "_audit", None),
                             surfaces={"cli": None})

    result = service.finalize(TASK_ID)

    assert not result.ready
    assert _failed(result)[0] == "configuration" and "surfaces" in _failed(result)
    assert len(result.blocking_issues) == len(_failed(result)) >= 2


def test_warnings_never_block():
    _, _, service = _service(persist=False, surfaces={})

    result = service.finalize()

    warned = [c.name for c in result.checks if c.status == FINALIZATION_CHECK_WARNING]
    assert result.ready and result.blocking_issues == ()
    assert {"decision_lineage", "critical_blockers", "persisted_results", "surfaces"} <= set(warned)
    assert len(result.warnings) == len(warned)


def test_repeated_finalization_is_deterministic_and_read_only():
    f, _, service = _service()
    calls, audits = list(f.calls.log), list(f.audit.list(TASK_ID))

    first, second = service.finalize(TASK_ID), service.finalize(TASK_ID)

    assert first == second
    assert f.calls.log == calls and f.audit.list(TASK_ID) == audits


def test_blank_task_id_is_rejected():
    _, _, service = _service()
    for bad in ("", 5):
        with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionLifecycleFinalizationError):
            service.finalize(bad)


def test_latest_blocked_lifecycle_result_is_a_critical_blocker():
    _, _, service = _service(fixture=_VerifyFixture(fail={"invalidate"}))

    result = service.finalize(TASK_ID)

    assert not result.ready and _failed(result) == ["critical_blockers"]
    assert "blocked" in result.blocking_issues[0]
