import pytest

from backend.agent_capability_execution import (
    FAILED,
    RUNNING,
    SUCCEEDED,
    InvalidCapabilityExecutionError,
    JsonExecutionStore,
    LLMAgentCapabilityExecution,
    LLMAgentCapabilityExecutionService,
    TerminalCapabilityExecutionError,
    UnknownCapabilityExecutionError,
)


def _service():
    return LLMAgentCapabilityExecutionService()


def test_start_complete_lifecycle():
    service = _service()

    execution = service.start("agent-1", "web-search", "1.0.0", "scope-1", input_data={"query": "x"})

    assert isinstance(execution, LLMAgentCapabilityExecution)
    assert execution.status == RUNNING
    assert execution.completed_at is None
    assert execution.input_reference is not None
    assert execution.input_reference.startswith("sha256:")

    completed = service.complete(execution.execution_id, result={"results": [1, 2]})

    assert completed.status == SUCCEEDED
    assert completed.completed_at is not None
    assert completed.output_reference is not None
    assert completed.output_reference.startswith("sha256:")
    assert completed.error is None
    # identity fields are preserved across the transition
    assert completed.execution_id == execution.execution_id
    assert completed.agent_id == "agent-1"
    assert completed.capability_id == "web-search"
    assert completed.capability_version == "1.0.0"
    assert completed.scope_id == "scope-1"


def test_start_fail_lifecycle():
    service = _service()
    execution = service.start("agent-1", "web-search", "1.0.0", "scope-1")

    failed = service.fail(execution.execution_id, ValueError("boom"))

    assert failed.status == FAILED
    assert failed.completed_at is not None
    assert failed.error == "boom"
    assert failed.output_reference is None


def test_invalid_state_transitions_rejected():
    service = _service()
    execution = service.start("agent-1", "web-search", "1.0.0", "scope-1")
    service.complete(execution.execution_id, result="ok")

    with pytest.raises(TerminalCapabilityExecutionError):
        service.complete(execution.execution_id, result="again")
    with pytest.raises(TerminalCapabilityExecutionError):
        service.fail(execution.execution_id, "too late")

    failed_execution = service.start("agent-1", "web-search", "1.0.0", "scope-1")
    service.fail(failed_execution.execution_id, "boom")
    with pytest.raises(TerminalCapabilityExecutionError):
        service.complete(failed_execution.execution_id, result="ok")
    with pytest.raises(TerminalCapabilityExecutionError):
        service.fail(failed_execution.execution_id, "again")


def test_unknown_executions_are_rejected():
    service = _service()

    with pytest.raises(UnknownCapabilityExecutionError):
        service.get("missing-id")
    with pytest.raises(UnknownCapabilityExecutionError):
        service.complete("missing-id", result="ok")
    with pytest.raises(UnknownCapabilityExecutionError):
        service.fail("missing-id", "boom")


def test_exact_capability_version_preserved():
    service = _service()
    execution = service.start("agent-1", "web-search", "2.3.1", "scope-1")

    assert execution.capability_version == "2.3.1"
    fetched = service.get(execution.execution_id)
    assert fetched.capability_version == "2.3.1"

    completed = service.complete(execution.execution_id, result="ok")
    assert completed.capability_version == "2.3.1"


def test_agent_and_capability_filtering():
    service = _service()
    e1 = service.start("agent-1", "web-search", "1.0.0", "scope-1")
    e2 = service.start("agent-1", "code-exec", "1.0.0", "scope-1")
    e3 = service.start("agent-2", "web-search", "1.0.0", "scope-1")

    by_agent = service.list_for_agent("agent-1")
    assert {execution.execution_id for execution in by_agent} == {e1.execution_id, e2.execution_id}

    by_capability = service.list_for_capability("web-search")
    assert {execution.execution_id for execution in by_capability} == {e1.execution_id, e3.execution_id}

    assert service.list_for_agent("nonexistent-agent") == []
    assert service.list_for_capability("nonexistent-capability") == []


def test_sensitive_data_handling_follows_existing_repository_rules():
    service = _service()
    execution = service.start(
        "agent-1", "web-search", "1.0.0", "scope-1", input_data={"api_key": "sk-abcdefghijklmnop"}
    )

    # the raw secret never reaches the stored record in any form
    assert "sk-abcdefghijklmnop" not in str(execution.input_reference)
    assert execution.input_reference.startswith("sha256:")

    completed = service.complete(execution.execution_id, result={"token": "Bearer abc123xyz"})
    assert "abc123xyz" not in str(completed.output_reference)

    failed_execution = service.start("agent-1", "web-search", "1.0.0", "scope-1")
    failed = service.fail(failed_execution.execution_id, "auth failed: api_key=sk-abcdefghijklmnop")
    assert "sk-abcdefghijklmnop" not in failed.error
    assert "[REDACTED]" in failed.error


def test_terminal_records_cannot_be_mutated_incorrectly():
    service = _service()
    execution = service.start("agent-1", "web-search", "1.0.0", "scope-1")
    completed = service.complete(execution.execution_id, result="first-result")

    with pytest.raises(TerminalCapabilityExecutionError):
        service.complete(execution.execution_id, result="second-result")

    unchanged = service.get(execution.execution_id)
    assert unchanged == completed
    assert unchanged.output_reference == completed.output_reference


def test_start_validation():
    service = _service()

    with pytest.raises(InvalidCapabilityExecutionError):
        service.start("", "web-search", "1.0.0", "scope-1")
    with pytest.raises(InvalidCapabilityExecutionError):
        service.start("agent-1", "", "1.0.0", "scope-1")
    with pytest.raises(InvalidCapabilityExecutionError):
        service.start("agent-1", "web-search", "", "scope-1")
    with pytest.raises(InvalidCapabilityExecutionError):
        service.start("agent-1", "web-search", "1.0.0", "")


def test_fail_requires_a_non_blank_error():
    service = _service()
    execution = service.start("agent-1", "web-search", "1.0.0", "scope-1")

    with pytest.raises(InvalidCapabilityExecutionError):
        service.fail(execution.execution_id, "")
    with pytest.raises(InvalidCapabilityExecutionError):
        service.fail(execution.execution_id, None)


def test_json_store_round_trip(tmp_path):
    path = tmp_path / "executions.json"

    service1 = LLMAgentCapabilityExecutionService(store=JsonExecutionStore(path))
    execution = service1.start("agent-1", "web-search", "1.0.0", "scope-1", input_data={"query": "x"})
    service1.complete(execution.execution_id, result={"ok": True})

    service2 = LLMAgentCapabilityExecutionService(store=JsonExecutionStore(path))
    fetched = service2.get(execution.execution_id)
    assert fetched.status == SUCCEEDED
    assert fetched.capability_version == "1.0.0"
    assert fetched.output_reference.startswith("sha256:")
