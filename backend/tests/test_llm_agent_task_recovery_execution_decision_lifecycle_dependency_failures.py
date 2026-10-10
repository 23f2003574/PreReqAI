from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    IMPACT_LIFECYCLE_EXECUTION_FAILED,
    IMPACT_LIFECYCLE_REMEDIATED,
    IMPACT_LIFECYCLE_UNSAFE,
)
from lifecycle_support import _lifecycle
from test_llm_agent_task_recovery_execution_decision_impact_invalidation_lifecycle import TASK_ID, _VerifyFixture


def _boom(*args, **kwargs):
    raise ConnectionError("dependency down")


# stage label -> the lifecycle keyword whose collaborator fails, and the method that raises
PRE_MUTATION_FAILURES = {
    "decision resolution": ("resolution", "resolve"),
    "impact analysis": ("impact_service", "analyze"),
    "artifact staleness": ("staleness_service", "check"),
    "remediation planning": ("plan_service", "plan"),
    "plan validation": ("plan_validation_service", "validate"),
}


@pytest.mark.parametrize("stage", sorted(PRE_MUTATION_FAILURES))
def test_prerequisite_failure_fails_cleanly_and_never_mutates(stage):
    f = _VerifyFixture(same_snapshot=True)
    keyword, method = PRE_MUTATION_FAILURES[stage]
    double = SimpleNamespace(**{method: _boom})
    overrides = {"resolution": double} if keyword == "resolution" else {keyword: double}

    result = _lifecycle(f, **overrides).run(TASK_ID)

    assert result.status == IMPACT_LIFECYCLE_EXECUTION_FAILED
    assert result.errors == (f"{stage} failed: ConnectionError: dependency down",)
    assert f.calls.log == [] and f.audit.list(TASK_ID) == []
    assert result.operation_id is None and result.applied == () and result.verification is None


def test_failure_after_planning_keeps_the_decision_context():
    f = _VerifyFixture(same_snapshot=True)

    result = _lifecycle(f, plan_validation_service=SimpleNamespace(validate=_boom)).run(TASK_ID)

    assert (result.previous_decision_id, result.authoritative_decision_id) == ("d1", "d2")
    assert result.planned_actions and result.affected_artifacts


def test_audit_failure_after_mutation_is_reported_not_success():
    f = _VerifyFixture(same_snapshot=True)

    result = _lifecycle(f, audit_service=SimpleNamespace(record=_boom, list=lambda task_id: [])).run(TASK_ID)

    assert result.status == IMPACT_LIFECYCLE_EXECUTION_FAILED
    assert any("recording the audit failed: ConnectionError" in e for e in result.errors)
    assert result.applied  # the mutation that already ran is still reported truthfully


def test_verification_failure_is_unsafe_with_the_original_error_kept():
    f = _VerifyFixture(same_snapshot=True)

    result = _lifecycle(f, verification_service=SimpleNamespace(verify=_boom)).run(TASK_ID)

    assert result.status == IMPACT_LIFECYCLE_UNSAFE
    assert any("verification failed: ConnectionError: dependency down" in e for e in result.errors)


def test_failed_run_preserves_earlier_audit_history_and_recovers_on_the_next_run():
    f = _VerifyFixture(same_snapshot=True)
    first = _lifecycle(f).run(TASK_ID)
    assert first.status == IMPACT_LIFECYCLE_REMEDIATED
    audits_before = f.audit.list(TASK_ID)

    failed = _lifecycle(f, staleness_service=SimpleNamespace(check=_boom)).run(TASK_ID)

    assert failed.status == IMPACT_LIFECYCLE_EXECUTION_FAILED
    assert f.audit.list(TASK_ID) == audits_before
