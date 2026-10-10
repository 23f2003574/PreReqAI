"""Tests for the `recovery-decision diagnose` CLI command (backend/cli.py).

A fake health_service -- returning the real #6/#7 result contract
(AgentTaskRecoveryExecutionDecisionLifecycleHealthResult, carrying
AgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnostic entries)
built directly -- exercises the CLI's own parsing/formatting/exit-code
logic in isolation, the same fixture-reuse approach test_recovery_decision_cli.py
already uses for `evaluate`. diagnose is diagnostic-only: these tests
also confirm it never touches the facade/evaluate path.
"""

import json

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    AgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnostic,
    AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck,
    AgentTaskRecoveryExecutionDecisionLifecycleHealthResult,
    DEPENDENCY_ORDER,
    HEALTH_BLOCKED,
    HEALTH_DEGRADED,
    HEALTH_HEALTHY,
    HEALTH_UNAVAILABLE,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleHealthError,
)

from backend.cli import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, main


def _dependency_diagnostics(status=HEALTH_HEALTHY, failure_reason=None, blocking=False):
    return tuple(
        AgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnostic(
            dependency=name,
            status=status if name == DEPENDENCY_ORDER[0] else HEALTH_HEALTHY,
            failure_reason=failure_reason if name == DEPENDENCY_ORDER[0] else None,
            last_verified_state="ok",
            blocking=blocking if name == DEPENDENCY_ORDER[0] else False,
        )
        for name in DEPENDENCY_ORDER
    )


def _result(**overrides):
    fields = dict(
        task_id="task-1",
        status=HEALTH_HEALTHY,
        checks=(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck("decision_store_availability", True, "ok"),),
        issues=(),
        authoritative_decision_id="d1",
        latest_lifecycle_result_id="result-1",
        dependency_diagnostics=_dependency_diagnostics(),
    )
    fields.update(overrides)
    return AgentTaskRecoveryExecutionDecisionLifecycleHealthResult(**fields)


class _FakeHealthService:
    def __init__(self, result=None, error=None):
        self._result, self._error = result, error
        self.calls = []

    def check(self, task_id):
        self.calls.append(task_id)
        if self._error is not None:
            raise self._error
        return self._result


class _ExplodingFacade:
    """Any call proves diagnose() reached the facade -- it must never."""

    def evaluate(self, task_id):
        raise AssertionError("diagnose must never call facade.evaluate()")


def test_healthy_state_prints_required_fields_and_exits_zero(capsys):
    health_service = _FakeHealthService(_result())

    exit_code = main(
        ["recovery-decision", "diagnose", "task-1"], facade=_ExplodingFacade(), health_service=health_service,
    )

    out = capsys.readouterr().out
    assert exit_code == EXIT_OK
    assert health_service.calls == ["task-1"]
    assert "overall status: healthy" in out
    assert "authoritative decision: d1" in out
    assert "latest lifecycle result: result-1" in out
    for name in DEPENDENCY_ORDER:
        assert name in out


def test_degraded_state_exits_non_zero_and_reports_the_dependency(capsys):
    health_service = _FakeHealthService(_result(
        status=HEALTH_DEGRADED,
        dependency_diagnostics=_dependency_diagnostics(
            status=HEALTH_DEGRADED, failure_reason="no persisted lifecycle result found for task_id",
        ),
    ))

    exit_code = main(["recovery-decision", "diagnose", "task-1"], health_service=health_service)

    out = capsys.readouterr().out
    assert exit_code == EXIT_FAILURE
    assert "overall status: degraded" in out
    assert "no persisted lifecycle result found for task_id" in out


def test_blocked_state_exits_non_zero_and_marks_the_blocking_dependency(capsys):
    health_service = _FakeHealthService(_result(
        status=HEALTH_BLOCKED,
        dependency_diagnostics=_dependency_diagnostics(
            status=HEALTH_BLOCKED, failure_reason="3 blocking artifact(s)", blocking=True,
        ),
    ))

    exit_code = main(["recovery-decision", "diagnose", "task-1"], health_service=health_service)

    out = capsys.readouterr().out
    assert exit_code == EXIT_FAILURE
    assert "overall status: blocked" in out
    assert "blocking=True" in out
    assert "3 blocking artifact(s)" in out


def test_unavailable_state_exits_non_zero_and_distinguishes_infra_failure(capsys):
    health_service = _FakeHealthService(_result(
        status=HEALTH_UNAVAILABLE,
        dependency_diagnostics=_dependency_diagnostics(
            status=HEALTH_UNAVAILABLE, failure_reason="RuntimeError: store down", blocking=True,
        ),
    ))

    exit_code = main(["recovery-decision", "diagnose", "task-1"], health_service=health_service)

    out = capsys.readouterr().out
    assert exit_code == EXIT_FAILURE
    assert "overall status: unavailable" in out
    assert "store down" in out


def test_json_mode_emits_the_health_result_contract(capsys):
    health_service = _FakeHealthService(_result())

    exit_code = main(["recovery-decision", "diagnose", "task-1", "--json"], health_service=health_service)

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == EXIT_OK
    assert payload["status"] == HEALTH_HEALTHY
    assert len(payload["dependency_diagnostics"]) == len(DEPENDENCY_ORDER)


def test_malformed_task_id_exits_non_zero_without_a_stack_trace(capsys):
    health_service = _FakeHealthService(error=InvalidAgentTaskRecoveryExecutionDecisionLifecycleHealthError(
        "task_id is required and must be a non-empty string"
    ))

    exit_code = main(["recovery-decision", "diagnose", ""], health_service=health_service)

    captured = capsys.readouterr()
    assert exit_code == EXIT_FAILURE
    assert "task_id is required" in captured.err
    assert "Traceback" not in captured.err and "Traceback" not in captured.out


def test_missing_task_case_uses_the_real_wired_health_service_and_fails_closed(capsys):
    """No health_service injected -> the CLI builds and calls the real,
    production-wired LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService.
    A task with no recorded decisions has nothing to diagnose as healthy,
    so this fails closed as blocked rather than crashing."""
    exit_code = main(["recovery-decision", "diagnose", "never-seen-task"])

    out = capsys.readouterr().out
    assert exit_code == EXIT_FAILURE
    assert "overall status: blocked" in out
    assert "authoritative decision: None" in out


def test_missing_task_id_argument_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["recovery-decision", "diagnose"])

    assert excinfo.value.code == EXIT_USAGE
    assert "Traceback" not in capsys.readouterr().err


def test_diagnose_is_kept_separate_from_evaluate_and_never_touches_the_facade(capsys):
    """diagnose must be diagnostic-only: passing an evaluate()-exploding
    facade alongside a working health_service must not raise, proving
    diagnose() never reaches the facade."""
    health_service = _FakeHealthService(_result())

    exit_code = main(
        ["recovery-decision", "diagnose", "task-1"], facade=_ExplodingFacade(), health_service=health_service,
    )

    assert exit_code == EXIT_OK
