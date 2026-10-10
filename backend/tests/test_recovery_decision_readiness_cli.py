"""Tests for the `recovery-decision readiness` CLI command (backend/cli.py).

A fake readiness_service -- returning the real #13 result contract built
directly -- exercises the CLI's own parsing/formatting/exit-code logic
in isolation, the same fixture-reuse approach test_recovery_decision_cli.py
(#3) and test_recovery_decision_diagnose_cli.py (#8) already use.
readiness is diagnostic-only: also confirms it never touches the
facade/evaluate path.
"""

import json

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    AgentTaskRecoveryExecutionDecisionLifecycleReadinessResult,
    HEALTH_HEALTHY,
    HEALTH_UNAVAILABLE,
    LINEAGE_INVALID,
    LINEAGE_NOT_APPLICABLE,
    READINESS_BLOCKED,
    READINESS_VERIFICATION_NOT_APPLICABLE,
    READY,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleReadinessError,
)

from backend.cli import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, main


def _result(**overrides):
    fields = dict(
        status=READY,
        issues=(),
        configuration_status="valid",
        dependency_status=HEALTH_HEALTHY,
        decision_lineage_status=LINEAGE_NOT_APPLICABLE,
        verification_status=READINESS_VERIFICATION_NOT_APPLICABLE,
        blocking_conditions=(),
    )
    fields.update(overrides)
    return AgentTaskRecoveryExecutionDecisionLifecycleReadinessResult(**fields)


class _FakeReadinessService:
    def __init__(self, result=None, error=None):
        self._result, self._error = result, error
        self.calls = []

    def check(self, task_id=None):
        self.calls.append(task_id)
        if self._error is not None:
            raise self._error
        return self._result


class _ExplodingFacade:
    def evaluate(self, task_id):
        raise AssertionError("readiness must never call facade.evaluate()")


def test_ready_environment_with_no_task_id_prints_required_fields_and_exits_zero(capsys):
    readiness_service = _FakeReadinessService(_result())

    exit_code = main(["recovery-decision", "readiness"], facade=_ExplodingFacade(), readiness_service=readiness_service)

    out = capsys.readouterr().out
    assert exit_code == EXIT_OK
    assert readiness_service.calls == [None]
    assert "status: ready" in out
    assert "configuration status: valid" in out
    assert "dependency status: healthy" in out


def test_blocked_environment_exits_non_zero_and_reports_issues(capsys):
    readiness_service = _FakeReadinessService(_result(
        status=READINESS_BLOCKED,
        configuration_status="invalid",
        issues=("configuration: missing dependency staleness_service",),
    ))

    exit_code = main(["recovery-decision", "readiness"], readiness_service=readiness_service)

    out = capsys.readouterr().out
    assert exit_code == EXIT_FAILURE
    assert "status: blocked" in out
    assert "missing dependency staleness_service" in out


def test_task_scoped_readiness_reports_lineage_and_dependency_status(capsys):
    readiness_service = _FakeReadinessService(_result(
        status=READINESS_BLOCKED,
        dependency_status=HEALTH_UNAVAILABLE,
        decision_lineage_status=LINEAGE_INVALID,
    ))

    exit_code = main(["recovery-decision", "readiness", "task-1"], readiness_service=readiness_service)

    out = capsys.readouterr().out
    assert exit_code == EXIT_FAILURE
    assert readiness_service.calls == ["task-1"]
    assert "dependency status: unavailable" in out
    assert "decision lineage status: invalid" in out


def test_json_mode_emits_the_readiness_result_contract(capsys):
    readiness_service = _FakeReadinessService(_result())

    exit_code = main(["recovery-decision", "readiness", "--json"], readiness_service=readiness_service)

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == EXIT_OK
    assert payload["status"] == READY


def test_malformed_task_id_exits_non_zero_without_a_stack_trace(capsys):
    readiness_service = _FakeReadinessService(error=InvalidAgentTaskRecoveryExecutionDecisionLifecycleReadinessError(
        "task_id must be a non-empty string when given"
    ))

    exit_code = main(["recovery-decision", "readiness", ""], readiness_service=readiness_service)

    captured = capsys.readouterr()
    assert exit_code == EXIT_FAILURE
    assert "task_id must be" in captured.err
    assert "Traceback" not in captured.err and "Traceback" not in captured.out


def test_missing_task_uses_the_real_wired_readiness_service_and_fails_closed(capsys):
    exit_code = main(["recovery-decision", "readiness", "never-seen-task"])

    out = capsys.readouterr().out
    assert exit_code == EXIT_FAILURE
    assert "status: blocked" in out


def test_readiness_is_kept_separate_from_evaluate_and_never_touches_the_facade(capsys):
    readiness_service = _FakeReadinessService(_result())

    exit_code = main(
        ["recovery-decision", "readiness"], facade=_ExplodingFacade(), readiness_service=readiness_service,
    )

    assert exit_code == EXIT_OK


def test_missing_recovery_decision_subcommand_is_still_a_usage_error(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["recovery-decision"])

    assert excinfo.value.code == EXIT_USAGE
    assert "Traceback" not in capsys.readouterr().err
