import pytest

from backend.agent_capability_execution import (
    FAILED,
    RUNNING,
    SUCCEEDED,
    LLMAgentCapabilityExecutionService,
    UnknownCapabilityExecutionError,
)
from backend.agent_capability_execution_recovery import (
    CapabilityRecoveryResult,
    LLMAgentCapabilityRecoveryService,
    RecoveryCheck,
)
from backend.llm.tool_execution import LLMToolExecutionService
from backend.llm.tool_permissions import LLMToolPermissionService
from backend.llm.tool_retry import LLMToolRetryPolicy, LLMToolRetryService
from backend.llm.tools import LLMToolRegistryService


def _retry_service(*retryable_errors):
    """A real LLMToolRetryService wired with the minimal (unused, for
    should_retry()'s own purposes) collaborators its constructor
    requires -- should_retry() itself never touches them, only the
    policy given here."""
    registry = LLMToolRegistryService()
    permission_service = LLMToolPermissionService(registry)
    execution_service = LLMToolExecutionService(registry, permission_service)
    return LLMToolRetryService(
        execution_service=execution_service, policy=LLMToolRetryPolicy(retryable_errors=retryable_errors)
    )


class _FlakyError(Exception):
    pass


def _services(retry_service=None):
    execution_service = LLMAgentCapabilityExecutionService()
    recovery_service = LLMAgentCapabilityRecoveryService(execution_service, retry_service=retry_service)
    return execution_service, recovery_service


def test_recoverable_running_execution_is_detected():
    execution_service, recovery_service = _services()
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")

    check = recovery_service.can_recover(execution.execution_id)

    assert isinstance(check, RecoveryCheck)
    assert check.recoverable is True
    assert check.status == RUNNING


def test_terminal_succeeded_execution_is_rejected():
    execution_service, recovery_service = _services()
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")
    execution_service.complete(execution.execution_id, result="ok")

    check = recovery_service.can_recover(execution.execution_id)

    assert check.recoverable is False
    assert check.status == SUCCEEDED


def test_failed_execution_without_retry_service_is_not_recoverable():
    execution_service, recovery_service = _services()
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")
    execution_service.fail(execution.execution_id, "boom")

    check = recovery_service.can_recover(execution.execution_id)

    assert check.recoverable is False
    assert check.status == FAILED


def test_failed_execution_with_retryable_error_is_recoverable():
    retry_service = _retry_service(_FlakyError)
    execution_service, recovery_service = _services(retry_service=retry_service)
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")
    execution_service.fail(execution.execution_id, _FlakyError("transient glitch"))

    check = recovery_service.can_recover(execution.execution_id)

    assert check.recoverable is True


def test_failed_execution_with_non_retryable_error_is_rejected():
    retry_service = _retry_service(_FlakyError)
    execution_service, recovery_service = _services(retry_service=retry_service)
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")
    execution_service.fail(execution.execution_id, ValueError("permanent problem"))

    check = recovery_service.can_recover(execution.execution_id)

    assert check.recoverable is False


def test_recovering_running_execution_closes_it_as_failed_and_preserves_provenance():
    execution_service, recovery_service = _services()
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1", input_data={"q": "x"})

    result = recovery_service.recover(execution.execution_id)

    assert isinstance(result, CapabilityRecoveryResult)
    assert result.recoverable is True
    assert result.previous_status == RUNNING
    assert result.new_status == FAILED
    assert "interrupted" in result.reason or "RUNNING" in result.reason

    recovered = execution_service.get(execution.execution_id)
    assert recovered.status == FAILED
    assert recovered.agent_id == execution.agent_id
    assert recovered.capability_id == execution.capability_id
    assert recovered.capability_version == execution.capability_version
    assert recovered.scope_id == execution.scope_id
    assert recovered.input_reference == execution.input_reference
    assert recovered.started_at == execution.started_at


def test_recovering_retryable_failed_execution_does_not_mutate_the_record():
    retry_service = _retry_service(_FlakyError)
    execution_service, recovery_service = _services(retry_service=retry_service)
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")
    failed = execution_service.fail(execution.execution_id, _FlakyError("transient glitch"))

    result = recovery_service.recover(execution.execution_id)

    assert result.recoverable is True
    assert result.previous_status == FAILED
    assert result.new_status == FAILED

    unchanged = execution_service.get(execution.execution_id)
    assert unchanged == failed


def test_recovering_succeeded_execution_leaves_state_consistent():
    execution_service, recovery_service = _services()
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")
    completed = execution_service.complete(execution.execution_id, result="ok")

    result = recovery_service.recover(execution.execution_id)

    assert result.recoverable is False
    assert result.previous_status == SUCCEEDED
    assert result.new_status == SUCCEEDED

    unchanged = execution_service.get(execution.execution_id)
    assert unchanged == completed


def test_recovering_non_retryable_failed_execution_leaves_state_consistent():
    retry_service = _retry_service(_FlakyError)
    execution_service, recovery_service = _services(retry_service=retry_service)
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")
    failed = execution_service.fail(execution.execution_id, ValueError("permanent problem"))

    result = recovery_service.recover(execution.execution_id)

    assert result.recoverable is False
    unchanged = execution_service.get(execution.execution_id)
    assert unchanged == failed


def test_recovery_does_not_duplicate_execution_records():
    execution_service, recovery_service = _services()
    execution = execution_service.start("agent-1", "web-search", "1.0.0", "scope-1")

    recovery_service.recover(execution.execution_id)

    records = execution_service.list_for_agent("agent-1")
    assert len(records) == 1
    assert records[0].execution_id == execution.execution_id


def test_unknown_execution_raises():
    _execution_service, recovery_service = _services()

    with pytest.raises(UnknownCapabilityExecutionError):
        recovery_service.can_recover("missing-id")
    with pytest.raises(UnknownCapabilityExecutionError):
        recovery_service.recover("missing-id")
