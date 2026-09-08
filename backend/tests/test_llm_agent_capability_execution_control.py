from datetime import timedelta

import pytest

from backend.agent_capability_execution import (
    FAILED,
    RUNNING,
    SUCCEEDED,
    LLMAgentCapabilityExecutionService,
    TerminalCapabilityExecutionError,
    UnknownCapabilityExecutionError,
)
from backend.agent_capability_execution_control import (
    ACTION_CANCELLED,
    ACTION_NONE,
    ACTION_TIMED_OUT,
    ExecutionControlResult,
    LLMAgentCapabilityExecutionControl,
)


def _services(default_timeout_seconds=None):
    execution_service = LLMAgentCapabilityExecutionService()
    control = LLMAgentCapabilityExecutionControl(execution_service, default_timeout_seconds=default_timeout_seconds)
    return execution_service, control


def test_active_execution_can_be_cancelled():
    execution_service, control = _services()
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1", input_data={"q": "x"})

    result = control.cancel(execution.execution_id, reason="user aborted")

    assert isinstance(result, ExecutionControlResult)
    assert result.action == ACTION_CANCELLED
    assert result.previous_status == RUNNING
    assert result.new_status == FAILED
    assert "user aborted" in result.reason

    record = execution_service.get(execution.execution_id)
    assert record.status == FAILED
    assert record.agent_id == execution.agent_id
    assert record.capability_id == execution.capability_id
    assert record.capability_version == execution.capability_version
    assert record.scope_id == execution.scope_id
    assert record.input_reference == execution.input_reference
    assert record.started_at == execution.started_at


def test_terminal_execution_cannot_be_cancelled():
    execution_service, control = _services()

    succeeded = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")
    completed = execution_service.complete(succeeded.execution_id, result="ok")
    result = control.cancel(succeeded.execution_id)
    assert result.action == ACTION_NONE
    assert result.previous_status == SUCCEEDED
    assert result.new_status == SUCCEEDED
    assert execution_service.get(succeeded.execution_id) == completed

    failed_execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")
    failed = execution_service.fail(failed_execution.execution_id, "boom")
    result = control.cancel(failed_execution.execution_id)
    assert result.action == ACTION_NONE
    assert result.new_status == FAILED
    assert execution_service.get(failed_execution.execution_id) == failed


def test_expired_execution_is_timed_out():
    execution_service, control = _services(default_timeout_seconds=10)
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")

    expired_now = execution.started_at + timedelta(seconds=11)
    result = control.check_timeout(execution.execution_id, now=expired_now)

    assert result.action == ACTION_TIMED_OUT
    assert result.previous_status == RUNNING
    assert result.new_status == FAILED

    record = execution_service.get(execution.execution_id)
    assert record.status == FAILED
    assert "timed out" in record.error


def test_non_expired_execution_remains_unchanged():
    execution_service, control = _services(default_timeout_seconds=10)
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")

    still_within_budget = execution.started_at + timedelta(seconds=1)
    result = control.check_timeout(execution.execution_id, now=still_within_budget)

    assert result.action == ACTION_NONE
    assert result.previous_status == RUNNING
    assert result.new_status == RUNNING

    unchanged = execution_service.get(execution.execution_id)
    assert unchanged == execution


def test_missing_deadline_is_handled_correctly():
    execution_service, control = _services(default_timeout_seconds=None)
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")

    far_future = execution.started_at + timedelta(days=365)
    result = control.check_timeout(execution.execution_id, now=far_future)

    assert result.action == ACTION_NONE
    assert "no deadline" in result.reason
    unchanged = execution_service.get(execution.execution_id)
    assert unchanged == execution


def test_completion_after_cancellation_is_rejected():
    execution_service, control = _services()
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")
    control.cancel(execution.execution_id)

    with pytest.raises(TerminalCapabilityExecutionError):
        execution_service.complete(execution.execution_id, result="too-late")


def test_completion_after_timeout_is_rejected():
    execution_service, control = _services(default_timeout_seconds=5)
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")
    control.check_timeout(execution.execution_id, now=execution.started_at + timedelta(seconds=6))

    with pytest.raises(TerminalCapabilityExecutionError):
        execution_service.complete(execution.execution_id, result="too-late")


def test_state_and_provenance_remain_consistent_after_timeout():
    execution_service, control = _services(default_timeout_seconds=5)
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1", input_data={"q": "x"})

    control.check_timeout(execution.execution_id, now=execution.started_at + timedelta(seconds=6))
    record = execution_service.get(execution.execution_id)

    assert record.agent_id == execution.agent_id
    assert record.capability_id == execution.capability_id
    assert record.capability_version == execution.capability_version
    assert record.scope_id == execution.scope_id
    assert record.input_reference == execution.input_reference
    assert record.started_at == execution.started_at


def test_unknown_execution_raises():
    _execution_service, control = _services()

    with pytest.raises(UnknownCapabilityExecutionError):
        control.cancel("missing-id")
    with pytest.raises(UnknownCapabilityExecutionError):
        control.check_timeout("missing-id")
