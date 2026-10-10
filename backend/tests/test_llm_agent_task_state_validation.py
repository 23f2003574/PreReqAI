from backend.agent_task_lifecycle import (
    CANCELLED,
    COMPLETED,
    CREATED,
    FAILED,
    PLANNED,
    READY,
    RUNNING,
    AgentTask,
    LLMAgentTaskLifecycleService,
)
from backend.agent_task_state_validation import (
    AgentTaskStateValidationResult,
    LLMAgentTaskStateValidator,
    TransitionValidationResult,
)


def _lifecycle_service():
    return LLMAgentTaskLifecycleService()


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


# --- validate(task): valid task passes --------------------------------------------------


def test_freshly_created_task_is_valid():
    task = _lifecycle_service().create(_definition())

    result = LLMAgentTaskStateValidator.validate(task)

    assert isinstance(result, AgentTaskStateValidationResult)
    assert result.valid is True
    assert result.errors == []
    assert result.current_state == CREATED
    assert result.target_state is None


def test_task_partway_through_lifecycle_is_valid():
    service = _lifecycle_service()
    task = service.create(_definition())
    service.transition(task.task_id, PLANNED)
    task = service.transition(task.task_id, READY)

    result = LLMAgentTaskStateValidator.validate(task)

    assert result.valid is True
    assert result.errors == []


def test_task_in_terminal_state_with_reason_is_valid_with_no_warnings():
    service = _lifecycle_service()
    task = service.create(_definition())
    service.transition(task.task_id, PLANNED)
    service.transition(task.task_id, READY)
    service.transition(task.task_id, RUNNING)
    task = service.transition(task.task_id, COMPLETED, reason="finished successfully")

    result = LLMAgentTaskStateValidator.validate(task)

    assert result.valid is True
    assert result.warnings == []


# --- validate(task): invalid state rejected -----------------------------------------------


def test_validate_rejects_unknown_current_state():
    task = AgentTask(agent_id="agent-1", scope_id="scope-1", objective="do something", current_state="bogus")

    result = LLMAgentTaskStateValidator.validate(task)

    assert result.valid is False
    assert result.current_state == "bogus"
    assert any("current_state" in error for error in result.errors)


def test_validate_rejects_unknown_previous_state():
    task = AgentTask(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="do something",
        current_state=PLANNED,
        previous_state="bogus",
    )

    result = LLMAgentTaskStateValidator.validate(task)

    assert result.valid is False
    assert any("previous_state" in error for error in result.errors)


def test_validate_rejects_non_agent_task_input():
    result = LLMAgentTaskStateValidator.validate({"current_state": CREATED})

    assert result.valid is False
    assert result.current_state is None
    assert any("AgentTask" in error for error in result.errors)


# --- validate(task): malformed/inconsistent state -----------------------------------------


def test_validate_rejects_created_state_with_a_previous_state():
    task = AgentTask(
        agent_id="agent-1", scope_id="scope-1", objective="do something", current_state=CREATED, previous_state=PLANNED
    )

    result = LLMAgentTaskStateValidator.validate(task)

    assert result.valid is False
    assert any("CREATED" in error or "previous_state" in error for error in result.errors)


def test_validate_rejects_non_created_state_missing_previous_state():
    task = AgentTask(agent_id="agent-1", scope_id="scope-1", objective="do something", current_state=RUNNING)

    result = LLMAgentTaskStateValidator.validate(task)

    assert result.valid is False
    assert any("previous_state" in error for error in result.errors)


def test_validate_rejects_previous_state_that_could_not_legally_reach_current_state():
    task = AgentTask(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="do something",
        current_state=RUNNING,
        previous_state=CREATED,
    )

    result = LLMAgentTaskStateValidator.validate(task)

    assert result.valid is False
    assert any("cannot legally reach" in error for error in result.errors)


def test_validate_rejects_missing_required_identity_fields():
    task = AgentTask(agent_id="", scope_id="scope-1", objective="do something")

    result = LLMAgentTaskStateValidator.validate(task)

    assert result.valid is False
    assert any("agent_id" in error for error in result.errors)


def test_validate_rejects_non_dict_definition():
    task = AgentTask(agent_id="agent-1", scope_id="scope-1", objective="do something", definition=None)

    result = LLMAgentTaskStateValidator.validate(task)

    assert result.valid is False
    assert any("definition" in error for error in result.errors)


def test_validate_warns_on_terminal_state_without_reason():
    task = AgentTask(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="do something",
        current_state=FAILED,
        previous_state=READY,
        transition_reason=None,
    )

    result = LLMAgentTaskStateValidator.validate(task)

    assert result.valid is True  # a missing reason is advisory only
    assert any("terminal state" in warning for warning in result.warnings)


# --- validate_transition: valid transition accepted ---------------------------------------


def test_validate_transition_accepts_legal_move():
    result = LLMAgentTaskStateValidator.validate_transition(CREATED, PLANNED)

    assert isinstance(result, TransitionValidationResult)
    assert result.valid is True
    assert result.errors == []
    assert result.current_state == CREATED
    assert result.target_state == PLANNED


def test_validate_transition_flags_self_transition_as_a_warning_not_an_error():
    result = LLMAgentTaskStateValidator.validate_transition(RUNNING, RUNNING)

    assert result.valid is True
    assert result.errors == []
    assert any("no-op" in warning for warning in result.warnings)


# --- validate_transition: invalid transition rejected --------------------------------------


def test_validate_transition_rejects_illegal_move():
    result = LLMAgentTaskStateValidator.validate_transition(CREATED, RUNNING)

    assert result.valid is False
    assert any("not permitted" in error for error in result.errors)


def test_validate_transition_rejects_unknown_current_state():
    result = LLMAgentTaskStateValidator.validate_transition("bogus", PLANNED)

    assert result.valid is False
    assert result.current_state == "bogus"
    assert any("current_state" in error for error in result.errors)


def test_validate_transition_rejects_unknown_target_state():
    result = LLMAgentTaskStateValidator.validate_transition(CREATED, "bogus")

    assert result.valid is False
    assert any("target_state" in error for error in result.errors)


# --- terminal-state transition rules enforced -----------------------------------------------


def test_validate_transition_rejects_leaving_a_terminal_state():
    result = LLMAgentTaskStateValidator.validate_transition(COMPLETED, PLANNED)

    assert result.valid is False
    assert any("terminal state" in error for error in result.errors)


def test_validate_transition_allows_terminal_state_self_transition():
    result = LLMAgentTaskStateValidator.validate_transition(CANCELLED, CANCELLED)

    assert result.valid is True


def test_is_terminal_matches_lifecycle_terminal_states():
    assert LLMAgentTaskStateValidator.is_terminal(COMPLETED) is True
    assert LLMAgentTaskStateValidator.is_terminal(FAILED) is True
    assert LLMAgentTaskStateValidator.is_terminal(CANCELLED) is True
    assert LLMAgentTaskStateValidator.is_terminal(RUNNING) is False
    assert LLMAgentTaskStateValidator.is_terminal("bogus") is False


# --- determinism -------------------------------------------------------------------------------


def test_validate_is_deterministic_across_repeated_calls():
    task = _lifecycle_service().create(_definition())

    first = LLMAgentTaskStateValidator.validate(task)
    second = LLMAgentTaskStateValidator.validate(task)

    assert first == second


def test_validate_transition_is_deterministic_across_repeated_calls():
    first = LLMAgentTaskStateValidator.validate_transition(READY, RUNNING)
    second = LLMAgentTaskStateValidator.validate_transition(READY, RUNNING)

    assert first == second
