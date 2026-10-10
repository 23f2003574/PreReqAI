"""Timeouts and cancellation at the lifecycle boundary. The lifecycle is
synchronous and the repository has no timeout primitive for it, so a dependency
timeout arrives as a raised TimeoutError; it must classify like any other
dependency failure (#11), and cancellation (a BaseException) must never be
swallowed."""
from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    IMPACT_LIFECYCLE_EXECUTION_FAILED,
    IMPACT_LIFECYCLE_UNSAFE,
    IMPACT_LIFECYCLE_UP_TO_DATE,
)
from lifecycle_support import _lifecycle
from test_llm_agent_task_recovery_execution_decision_impact_invalidation_lifecycle import TASK_ID, _VerifyFixture


def _timeout(*args, **kwargs):
    raise TimeoutError("timed out after 30s")


def _cancel(*args, **kwargs):
    raise KeyboardInterrupt()


def test_timeout_during_decision_resolution_is_a_non_success_result_without_mutation():
    f = _VerifyFixture(same_snapshot=True)

    result = _lifecycle(f, resolution=SimpleNamespace(resolve=_timeout)).run(TASK_ID)

    assert result.status == IMPACT_LIFECYCLE_EXECUTION_FAILED
    assert result.errors == ("decision resolution failed: TimeoutError: timed out after 30s",)
    assert f.calls.log == [] and f.audit.list(TASK_ID) == [] and result.operation_id is None


def test_timeout_during_remediation_stops_before_audit_and_verification():
    f = _VerifyFixture(same_snapshot=True)
    verified = []
    verifier = SimpleNamespace(verify=lambda *a: verified.append(a))

    result = _lifecycle(
        f, execution_service=SimpleNamespace(execute=_timeout), verification_service=verifier
    ).run(TASK_ID)

    assert result.status == IMPACT_LIFECYCLE_EXECUTION_FAILED and "TimeoutError" in result.errors[0]
    assert f.audit.list(TASK_ID) == [] and verified == []


def test_timeout_during_verification_is_unsafe_and_keeps_partial_progress():
    f = _VerifyFixture(same_snapshot=True)

    result = _lifecycle(f, verification_service=SimpleNamespace(verify=_timeout)).run(TASK_ID)

    audit = f.audit.list(TASK_ID)[0]
    assert result.status == IMPACT_LIFECYCLE_UNSAFE
    assert any("verification failed: TimeoutError" in e for e in result.errors)
    assert result.applied and result.operation_id == audit.operation_id and result.audit_id == audit.audit_id


def test_timeout_while_recording_the_audit_keeps_the_operation_id_and_skips_verification():
    f = _VerifyFixture(same_snapshot=True)
    verified = []

    result = _lifecycle(
        f, audit_service=SimpleNamespace(record=_timeout, list=lambda task_id: []),
        verification_service=SimpleNamespace(verify=lambda *a: verified.append(a)),
    ).run(TASK_ID)

    assert result.status == IMPACT_LIFECYCLE_EXECUTION_FAILED and verified == []
    assert result.operation_id is not None and result.applied and result.audit_id is None


@pytest.mark.parametrize("stage", ["resolution", "execution_service", "verification_service"])
def test_cancellation_is_never_swallowed(stage):
    f = _VerifyFixture(same_snapshot=True)
    double = SimpleNamespace(resolve=_cancel, execute=_cancel, verify=_cancel)

    with pytest.raises(KeyboardInterrupt):
        _lifecycle(f, **{stage: double}).run(TASK_ID)


def test_repeated_evaluation_after_a_verification_timeout_recovers_without_rerunning_audited_work():
    f = _VerifyFixture(same_snapshot=True)
    first = _lifecycle(f, verification_service=SimpleNamespace(verify=_timeout)).run(TASK_ID)
    calls_after_timeout = list(f.calls.log)

    second = _lifecycle(f).run(TASK_ID)

    assert first.status == IMPACT_LIFECYCLE_UNSAFE
    assert second.status == IMPACT_LIFECYCLE_UP_TO_DATE, second.errors
    assert len(f.audit.list(TASK_ID)) == 1
    assert f.calls.log == calls_after_timeout  # the audited work is not re-run
