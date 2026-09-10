import pytest

from backend.agent_task_lifecycle import (
    CANCELLED,
    COMPLETED,
    CREATED,
    FAILED,
    PAUSED,
    PLANNED,
    READY,
    RUNNING,
    STATES,
    TERMINAL_STATES,
    AgentTask,
    InvalidAgentTaskError,
    InvalidTaskTransitionError,
    JsonAgentTaskStore,
    JsonAgentTaskTransitionStore,
    LLMAgentTaskLifecycleService,
    UnknownAgentTaskError,
)


def _service():
    return LLMAgentTaskLifecycleService()


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


# --- create/get --------------------------------------------------------------------


def test_create_starts_in_created_state():
    service = _service()

    task = service.create(_definition())

    assert isinstance(task, AgentTask)
    assert task.agent_id == "agent-1"
    assert task.scope_id == "scope-1"
    assert task.objective == "summarize the notebook"
    assert task.current_state == CREATED
    assert task.previous_state is None
    assert task.transition_reason is None

    fetched = service.get(task.task_id)
    assert fetched == task


def test_create_preserves_extra_definition_fields():
    service = _service()

    task = service.create(_definition(priority="high"))

    assert task.definition["priority"] == "high"


def test_create_rejects_non_dict_definition():
    service = _service()

    with pytest.raises(InvalidAgentTaskError):
        service.create("not-a-dict")


@pytest.mark.parametrize("missing", ["agent_id", "scope_id", "objective"])
def test_create_rejects_missing_identity_fields(missing):
    service = _service()
    definition = _definition()
    definition.pop(missing)

    with pytest.raises(InvalidAgentTaskError):
        service.create(definition)


def test_create_honors_explicit_task_id():
    service = _service()

    task = service.create(_definition(task_id="task-123"))

    assert task.task_id == "task-123"
    assert service.get("task-123") == task


def test_create_rejects_blank_explicit_task_id():
    service = _service()

    with pytest.raises(InvalidAgentTaskError):
        service.create(_definition(task_id="   "))


def test_get_missing_task_raises():
    service = _service()

    with pytest.raises(UnknownAgentTaskError):
        service.get("does-not-exist")


# --- can_transition -----------------------------------------------------------------


@pytest.mark.parametrize(
    "current_state,target_state",
    [
        (CREATED, PLANNED),
        (CREATED, CANCELLED),
        (PLANNED, READY),
        (PLANNED, FAILED),
        (READY, RUNNING),
        (READY, FAILED),
        (RUNNING, COMPLETED),
        (RUNNING, FAILED),
        (RUNNING, PAUSED),
        (RUNNING, CANCELLED),
        (PAUSED, RUNNING),
        (PAUSED, CANCELLED),
    ],
)
def test_can_transition_reports_valid_edges(current_state, target_state):
    assert LLMAgentTaskLifecycleService.can_transition(current_state, target_state) is True


@pytest.mark.parametrize(
    "current_state,target_state",
    [
        (CREATED, RUNNING),
        (CREATED, COMPLETED),
        (PLANNED, RUNNING),
        (RUNNING, PLANNED),
        (COMPLETED, RUNNING),
        (FAILED, RUNNING),
        (CANCELLED, RUNNING),
    ],
)
def test_can_transition_rejects_invalid_edges(current_state, target_state):
    assert LLMAgentTaskLifecycleService.can_transition(current_state, target_state) is False


def test_can_transition_rejects_unknown_states():
    assert LLMAgentTaskLifecycleService.can_transition("bogus", CREATED) is False
    assert LLMAgentTaskLifecycleService.can_transition(CREATED, "bogus") is False


def test_can_transition_allows_self_transition_even_from_terminal_state():
    for state in STATES:
        assert LLMAgentTaskLifecycleService.can_transition(state, state) is True


# --- valid transitions ---------------------------------------------------------------


def test_valid_transition_updates_state_and_reason():
    service = _service()
    task = service.create(_definition())

    planned = service.transition(task.task_id, PLANNED, reason="planning started")

    assert planned.current_state == PLANNED
    assert planned.previous_state == CREATED
    assert planned.transition_reason == "planning started"

    ready = service.transition(task.task_id, READY)
    assert ready.current_state == READY
    assert ready.previous_state == PLANNED
    assert ready.transition_reason is None


def test_full_happy_path_to_completed():
    service = _service()
    task = service.create(_definition())

    service.transition(task.task_id, PLANNED)
    service.transition(task.task_id, READY)
    service.transition(task.task_id, RUNNING)
    completed = service.transition(task.task_id, COMPLETED, reason="finished successfully")

    assert completed.current_state == COMPLETED
    assert completed.previous_state == RUNNING
    assert completed.transition_reason == "finished successfully"


def test_running_can_pause_and_resume():
    service = _service()
    task = service.create(_definition())
    service.transition(task.task_id, PLANNED)
    service.transition(task.task_id, READY)
    service.transition(task.task_id, RUNNING)

    paused = service.transition(task.task_id, PAUSED, reason="waiting on a dependency")
    assert paused.current_state == PAUSED

    resumed = service.transition(task.task_id, RUNNING)
    assert resumed.current_state == RUNNING
    assert resumed.previous_state == PAUSED


# --- invalid transitions ---------------------------------------------------------------


def test_invalid_transition_rejected():
    service = _service()
    task = service.create(_definition())

    with pytest.raises(InvalidTaskTransitionError):
        service.transition(task.task_id, RUNNING)

    # State is untouched by the rejected attempt.
    assert service.get(task.task_id).current_state == CREATED


def test_transition_rejects_unknown_target_state():
    service = _service()
    task = service.create(_definition())

    with pytest.raises(InvalidTaskTransitionError):
        service.transition(task.task_id, "not-a-real-state")


def test_transition_missing_task_raises():
    service = _service()

    with pytest.raises(UnknownAgentTaskError):
        service.transition("does-not-exist", PLANNED)


def test_transition_rejects_non_string_reason():
    service = _service()
    task = service.create(_definition())

    with pytest.raises(InvalidAgentTaskError):
        service.transition(task.task_id, PLANNED, reason=123)


# --- terminal-state behavior -----------------------------------------------------------


@pytest.mark.parametrize("terminal_state", sorted(TERMINAL_STATES))
def test_terminal_state_rejects_further_progress(terminal_state):
    service = _service()
    task = service.create(_definition())
    service.transition(task.task_id, PLANNED)
    service.transition(task.task_id, READY)
    if terminal_state == COMPLETED:
        service.transition(task.task_id, RUNNING)
    service.transition(task.task_id, terminal_state, reason="reaching terminal state")

    with pytest.raises(InvalidTaskTransitionError):
        service.transition(task.task_id, PLANNED)


def test_terminal_state_self_transition_is_a_noop():
    service = _service()
    task = service.create(_definition())
    service.transition(task.task_id, PLANNED)
    service.transition(task.task_id, READY)
    service.transition(task.task_id, FAILED, reason="ready check failed")

    before = service.get(task.task_id)
    again = service.transition(task.task_id, FAILED, reason="ignored second reason")

    assert again == before
    assert again.transition_reason == "ready check failed"
    # CREATED, CREATED->PLANNED, PLANNED->READY, READY->FAILED -- the repeated
    # FAILED->FAILED call above added nothing new.
    assert len(service.history(task.task_id)) == 4


# --- repeated transition (idempotency) ---------------------------------------------------


def test_repeated_same_state_transition_is_idempotent_noop():
    service = _service()
    task = service.create(_definition())
    planned = service.transition(task.task_id, PLANNED, reason="first reason")

    again = service.transition(task.task_id, PLANNED, reason="a different reason")

    assert again.current_state == PLANNED
    assert again.previous_state == planned.previous_state
    assert again.transition_reason == planned.transition_reason == "first reason"
    assert again == planned
    # No new history entry was appended for the no-op call.
    assert len(service.history(task.task_id)) == 2  # CREATED, CREATED->PLANNED


# --- transition history / reason persistence ---------------------------------------------


def test_history_records_every_successful_transition_in_order():
    service = _service()
    task = service.create(_definition())
    service.transition(task.task_id, PLANNED, reason="kick off planning")
    service.transition(task.task_id, READY, reason="dependencies resolved")
    service.transition(task.task_id, RUNNING)

    history = service.history(task.task_id)

    assert [record.to_state for record in history] == [CREATED, PLANNED, READY, RUNNING]
    assert history[0].from_state is None
    assert history[1].from_state == CREATED
    assert history[1].reason == "kick off planning"
    assert history[2].reason == "dependencies resolved"
    assert history[3].reason is None
    for earlier, later in zip(history, history[1:]):
        assert earlier.occurred_at <= later.occurred_at


def test_history_missing_task_raises():
    service = _service()

    with pytest.raises(UnknownAgentTaskError):
        service.history("does-not-exist")


def test_rejected_transition_does_not_add_history_entry():
    service = _service()
    task = service.create(_definition())

    with pytest.raises(InvalidTaskTransitionError):
        service.transition(task.task_id, RUNNING)

    assert len(service.history(task.task_id)) == 1  # only the initial CREATED entry


# --- JSON persistence ------------------------------------------------------------------


def test_json_stores_round_trip_across_service_instances(tmp_path):
    tasks_path = tmp_path / "tasks.json"
    transitions_path = tmp_path / "transitions.json"

    service_a = LLMAgentTaskLifecycleService(
        store=JsonAgentTaskStore(tasks_path),
        transition_store=JsonAgentTaskTransitionStore(transitions_path),
    )
    task = service_a.create(_definition())
    service_a.transition(task.task_id, PLANNED, reason="kick off planning")

    service_b = LLMAgentTaskLifecycleService(
        store=JsonAgentTaskStore(tasks_path),
        transition_store=JsonAgentTaskTransitionStore(transitions_path),
    )
    fetched = service_b.get(task.task_id)
    history = service_b.history(task.task_id)

    assert fetched.current_state == PLANNED
    assert fetched.transition_reason == "kick off planning"
    assert [record.to_state for record in history] == [CREATED, PLANNED]
