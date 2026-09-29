"""Tests for the `recovery-decision evaluate` CLI command (backend/cli.py).

A fake facade -- returning the real #2 result contract
(AgentTaskRecoveryExecutionDecisionLifecycleResult) built directly --
exercises the CLI's own parsing/formatting/exit-code logic in isolation,
the same fixture-reuse approach the facade's own tests use one layer
down: the CLI adds no business logic, so these tests prove it reports an
already-computed result correctly, not re-derive lifecycle outcomes that
already have their own coverage.
"""

import json

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    AgentTaskRecoveryExecutionDecisionLifecycleResult,
    IMPACT_LIFECYCLE_BLOCKED,
    IMPACT_LIFECYCLE_REMEDIATED,
    IMPACT_LIFECYCLE_UNRESOLVED,
    IMPACT_LIFECYCLE_UNSAFE,
    LIFECYCLE_VERIFICATION_INVALID,
    LIFECYCLE_VERIFICATION_VALID,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError,
)

from backend.cli import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, main


def _result(**overrides):
    fields = dict(
        task_id="task-1",
        authoritative_decision_id="d2",
        decision_lineage_status="valid",
        affected_artifacts=("authorization:d1",),
        remediation_operation_id="op-1",
        reconciliation_operation_id=None,
        blocking_conditions=(),
        verification_status=LIFECYCLE_VERIFICATION_VALID,
        overall_status=IMPACT_LIFECYCLE_REMEDIATED,
        diagnostics=(),
    )
    fields.update(overrides)
    return AgentTaskRecoveryExecutionDecisionLifecycleResult(**fields)


class _FakeFacade:
    def __init__(self, result=None, error=None):
        self._result, self._error = result, error
        self.calls = []

    def evaluate(self, task_id):
        self.calls.append(task_id)
        if self._error is not None:
            raise self._error
        return self._result


def test_successful_evaluation_prints_all_required_fields_and_exits_zero(capsys):
    facade = _FakeFacade(_result())

    exit_code = main(["recovery-decision", "evaluate", "task-1"], facade=facade)

    out = capsys.readouterr().out
    assert exit_code == EXIT_OK
    assert facade.calls == ["task-1"]
    for expected in (
        "authoritative decision: d2", "lineage status: valid", "authorization:d1",
        "remediation operation id: op-1", "reconciliation operation id: None",
        "blockers: none", "verification status: valid", "overall status: remediated",
    ):
        assert expected in out


def test_successful_evaluation_json_mode_emits_the_result_contract(capsys):
    facade = _FakeFacade(_result())

    exit_code = main(["recovery-decision", "evaluate", "task-1", "--json"], facade=facade)

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == EXIT_OK
    assert payload == _result().to_dict()


def test_blocked_evaluation_reports_blockers_and_exits_non_zero(capsys):
    facade = _FakeFacade(_result(
        overall_status=IMPACT_LIFECYCLE_BLOCKED,
        blocking_conditions=("authorization:d1", "preflight:d1"),
    ))

    exit_code = main(["recovery-decision", "evaluate", "task-1"], facade=facade)

    out = capsys.readouterr().out
    assert exit_code == EXIT_FAILURE
    assert "overall status: blocked" in out
    assert "authorization:d1, preflight:d1" in out


def test_failed_verification_exits_non_zero(capsys):
    facade = _FakeFacade(_result(
        overall_status=IMPACT_LIFECYCLE_UNSAFE,
        verification_status=LIFECYCLE_VERIFICATION_INVALID,
        diagnostics=("current decision fails its integrity check: tampered",),
    ))

    exit_code = main(["recovery-decision", "evaluate", "task-1"], facade=facade)

    out = capsys.readouterr().out
    assert exit_code == EXIT_FAILURE
    assert "verification status: invalid" in out
    assert "overall status: unsafe" in out


def test_malformed_task_id_exits_non_zero_without_a_stack_trace(capsys):
    facade = _FakeFacade(error=InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError(
        "task_id is required and must be a non-empty string"
    ))

    exit_code = main(["recovery-decision", "evaluate", ""], facade=facade)

    captured = capsys.readouterr()
    assert exit_code == EXIT_FAILURE
    assert "task_id is required" in captured.err
    assert "Traceback" not in captured.err and "Traceback" not in captured.out


def test_missing_task_case_uses_the_real_wired_facade_and_fails_closed(capsys):
    """No facade injected -> the CLI builds and calls the real,
    production-wired LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade.
    A task with no recorded decisions has no authoritative decision to
    resolve, so this fails closed as UNRESOLVED rather than crashing."""
    exit_code = main(["recovery-decision", "evaluate", "never-seen-task"])

    out = capsys.readouterr().out
    assert exit_code == EXIT_FAILURE
    assert "overall status: unresolved" in out
    assert "authoritative decision: None" in out


def test_missing_task_id_argument_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["recovery-decision", "evaluate"])

    assert excinfo.value.code == EXIT_USAGE
    assert "Traceback" not in capsys.readouterr().err


def test_unexpected_facade_error_is_reported_without_a_stack_trace(capsys):
    facade = _FakeFacade(error=RuntimeError("store unavailable"))

    exit_code = main(["recovery-decision", "evaluate", "task-1"], facade=facade)

    captured = capsys.readouterr()
    assert exit_code == EXIT_FAILURE
    assert "store unavailable" in captured.err
    assert "Traceback" not in captured.err
