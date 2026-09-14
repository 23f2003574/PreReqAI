from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_events import (
    CONTEXT_UPDATED,
    DEPENDENCY_ADDED,
    InMemoryAgentTaskEventStore,
    InvalidAgentTaskEventReplayError,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventReplayService,
    LLMAgentTaskEventService,
)
from backend.agent_task_lifecycle import (
    CANCELLED,
    CREATED,
    FAILED,
    PLANNED,
    READY,
    RUNNING,
)


def _services():
    store = InMemoryAgentTaskEventStore()
    emitter = LLMAgentTaskEventService(store=store)
    replay_service = LLMAgentTaskEventReplayService(LLMAgentTaskEventQueryService(store=store))
    return emitter, replay_service


# --- empty stream ----------------------------------------------------------------------------


def test_empty_stream_replays_to_created_with_no_transitions():
    _, replay_service = _services()

    result = replay_service.replay("task-1")

    assert result.task_id == "task-1"
    assert result.events_replayed == 0
    assert result.initial_state == CREATED
    assert result.final_state == CREATED
    assert result.state_transitions == ()
    assert result.replay_errors == ()


def test_replay_rejects_blank_task_id():
    _, replay_service = _services()

    with pytest.raises(InvalidAgentTaskEventReplayError):
        replay_service.replay("")


# --- normal lifecycle replay -------------------------------------------------------------------


def test_normal_lifecycle_replay_reaches_final_state():
    emitter, replay_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CREATED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})

    result = replay_service.replay("task-1")

    assert result.initial_state == CREATED
    assert result.final_state == READY
    assert result.events_replayed == 3
    assert result.replay_errors == ()


# --- multiple state transitions ------------------------------------------------------------------


def test_multiple_state_transitions_are_recorded_in_order():
    emitter, replay_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": RUNNING})

    result = replay_service.replay("task-1")

    assert [(t.from_state, t.to_state) for t in result.state_transitions] == [
        (CREATED, PLANNED),
        (PLANNED, READY),
        (READY, RUNNING),
    ]
    assert all(t.event_id for t in result.state_transitions)


def test_self_transition_reaffirmation_is_not_recorded_as_a_transition():
    emitter, replay_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})  # reaffirm, legal no-op

    result = replay_service.replay("task-1")

    assert len(result.state_transitions) == 1
    assert result.final_state == PLANNED
    assert result.replay_errors == ()


# --- invalid transition ----------------------------------------------------------------------------


def test_invalid_transition_is_reported_as_replay_error_not_applied():
    emitter, replay_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CREATED})
    bad_event = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": RUNNING})  # illegal jump
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})  # still legal from CREATED

    result = replay_service.replay("task-1")

    assert len(result.replay_errors) == 1
    assert result.replay_errors[0].event_id == bad_event.event_id
    # the rejected event never changed running state, so the later legal move still applies from CREATED
    assert result.final_state == PLANNED
    assert result.events_replayed == 3


def test_unrecognized_to_state_is_reported_as_replay_error():
    emitter, replay_service = _services()
    event = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "not-a-real-state"})

    result = replay_service.replay("task-1")

    assert len(result.replay_errors) == 1
    assert result.replay_errors[0].event_id == event.event_id
    assert result.final_state == CREATED


def test_terminal_state_blocks_further_transitions():
    emitter, replay_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})
    trailing = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CANCELLED})

    result = replay_service.replay("task-1")

    assert result.final_state == FAILED
    assert any(error.event_id == trailing.event_id for error in result.replay_errors)


# --- non-state-bearing events mixed into the stream -----------------------------------------------


def test_non_state_bearing_events_are_counted_but_ignored_for_state():
    emitter, replay_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    emitter.emit("task-1", DEPENDENCY_ADDED)
    emitter.emit("task-1", CONTEXT_UPDATED)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})

    result = replay_service.replay("task-1")

    assert result.events_replayed == 4
    assert result.final_state == READY
    assert len(result.state_transitions) == 2
    assert result.replay_errors == ()


def test_lifecycle_event_without_to_state_payload_is_skipped_not_errored():
    emitter, replay_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)  # no payload at all -- legitimate legacy event
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"note": "missing to_state"})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    result = replay_service.replay("task-1")

    assert result.events_replayed == 3
    assert result.replay_errors == ()
    assert result.final_state == PLANNED


# --- bounded / time-range replay --------------------------------------------------------------------


def test_bounded_time_range_replay_excludes_events_outside_window():
    emitter, replay_service = _services()
    t0 = datetime.now(timezone.utc)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CREATED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})
    cutoff = datetime.now(timezone.utc)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": RUNNING})

    result = replay_service.replay("task-1", start_time=t0 - timedelta(hours=1), end_time=cutoff)

    assert result.events_replayed == 3
    assert result.final_state == READY


def test_replay_rejects_non_datetime_time_bounds():
    _, replay_service = _services()

    with pytest.raises(Exception):
        replay_service.replay("task-1", start_time="not-a-datetime")


# --- deterministic repeated replay --------------------------------------------------------------------


def test_replay_is_deterministic_across_calls():
    emitter, replay_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": RUNNING})  # illegal from PLANNED
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})

    first = replay_service.replay("task-1")
    second = replay_service.replay("task-1")

    assert first == second


# --- replay never mutates stored task/event data -----------------------------------------------------


def test_replay_never_mutates_stored_events():
    emitter, replay_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    before = emitter.get("task-1")
    replay_service.replay("task-1")
    replay_service.replay("task-1")
    after = emitter.get("task-1")

    assert before == after
    assert len(after) == 1


def test_replay_never_emits_or_transitions_anything():
    emitter, replay_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    replay_service.replay("task-1")

    assert not hasattr(replay_service, "emit")
    assert not hasattr(replay_service, "transition")
    assert len(emitter.get("task-1")) == 1  # replay added nothing
