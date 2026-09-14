import pytest

from backend.agent_task_context import LLMAgentTaskContextService
from backend.agent_task_events import (
    CONFLICTING_TERMINAL,
    CONTEXT_UPDATED,
    IMPOSSIBLE_TRANSITION,
    InMemoryAgentTaskEventStore,
    INVALID_ORDER,
    INVALID_RELATIONSHIP,
    InvalidAgentTaskEventConsistencyError,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventConsistencyService,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
    MISSING_REFERENCE,
    STATE_MISMATCH,
)
from backend.agent_task_lifecycle import (
    COMPLETED,
    CREATED,
    FAILED,
    PLANNED,
    RUNNING,
    LLMAgentTaskLifecycleService,
    UnknownAgentTaskError,
)
from backend.agent_task_queue_retry_scheduler import LLMAgentTaskRetryScheduler
from backend.agent_task_state_history import LLMAgentTaskStateHistoryService


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _services():
    lifecycle_service = LLMAgentTaskLifecycleService()
    event_store = InMemoryAgentTaskEventStore()
    emitter = LLMAgentTaskEventService(store=event_store)
    query_service = LLMAgentTaskEventQueryService(store=event_store)
    consistency_service = LLMAgentTaskEventConsistencyService(lifecycle_service, query_service=query_service)
    return lifecycle_service, emitter, consistency_service


def _create_task(lifecycle_service):
    return lifecycle_service.create(_definition())


# --- valid event sequence -----------------------------------------------------------------


def test_valid_event_sequence_is_consistent():
    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": CREATED})
    emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    lifecycle_service.transition(task.task_id, PLANNED)

    result = consistency_service.validate(task.task_id)

    assert result.is_consistent is True
    assert result.violations == ()
    assert result.checked_event_count == 2
    assert result.checked_task_state == PLANNED


# --- empty event stream ----------------------------------------------------------------------


def test_empty_event_stream_is_consistent():
    lifecycle_service, _, consistency_service = _services()
    task = _create_task(lifecycle_service)

    result = consistency_service.validate(task.task_id)

    assert result.is_consistent is True
    assert result.violations == ()
    assert result.checked_event_count == 0
    assert result.checked_task_state == CREATED


def test_validate_rejects_blank_task_id():
    _, _, consistency_service = _services()

    with pytest.raises(InvalidAgentTaskEventConsistencyError):
        consistency_service.validate("")


def test_validate_raises_for_unknown_task():
    _, _, consistency_service = _services()

    with pytest.raises(UnknownAgentTaskError):
        consistency_service.validate("does-not-exist")


# --- invalid lifecycle transition ------------------------------------------------------------


def test_invalid_lifecycle_transition_is_flagged():
    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": CREATED})
    emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": RUNNING})  # CREATED -> RUNNING illegal

    result = consistency_service.validate(task.task_id)

    assert result.is_consistent is False
    assert any(violation.category == IMPOSSIBLE_TRANSITION for violation in result.violations)


def test_unrecognized_to_state_is_flagged_as_impossible_transition():
    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    event = emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": "not-a-real-state"})

    result = consistency_service.validate(task.task_id)

    assert any(
        violation.category == IMPOSSIBLE_TRANSITION and violation.event_id == event.event_id
        for violation in result.violations
    )


# --- conflicting terminal events --------------------------------------------------------------


def test_conflicting_terminal_events_are_flagged():
    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": COMPLETED})
    emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    result = consistency_service.validate(task.task_id)

    categories = {violation.category for violation in result.violations}
    assert CONFLICTING_TERMINAL in categories


def test_same_terminal_state_reported_twice_is_not_conflicting():
    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": COMPLETED})
    emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": COMPLETED})

    result = consistency_service.validate(task.task_id)

    assert all(violation.category != CONFLICTING_TERMINAL for violation in result.violations)


def test_activity_after_terminal_state_is_invalid_order():
    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": COMPLETED})
    trailing = emitter.emit(task.task_id, CONTEXT_UPDATED)

    result = consistency_service.validate(task.task_id)

    assert any(
        violation.category == INVALID_ORDER and violation.event_id == trailing.event_id
        for violation in result.violations
    )


# --- missing referenced object -----------------------------------------------------------------


def test_missing_state_history_reference_is_flagged():
    lifecycle_service, emitter, _ = _services()
    task = _create_task(lifecycle_service)
    event = emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    query_service = LLMAgentTaskEventQueryService(store=emitter.store)
    state_history_service = LLMAgentTaskStateHistoryService()  # empty: no matching record ever recorded
    consistency_service = LLMAgentTaskEventConsistencyService(
        lifecycle_service, query_service=query_service, state_history_service=state_history_service
    )

    result = consistency_service.validate(task.task_id)

    assert any(
        violation.category == MISSING_REFERENCE and violation.event_id == event.event_id
        for violation in result.violations
    )


def test_present_state_history_reference_is_not_flagged():
    lifecycle_service, emitter, _ = _services()
    task = _create_task(lifecycle_service)
    emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    query_service = LLMAgentTaskEventQueryService(store=emitter.store)
    state_history_service = LLMAgentTaskStateHistoryService()
    state_history_service.record_transition(task.task_id, CREATED, PLANNED)
    consistency_service = LLMAgentTaskEventConsistencyService(
        lifecycle_service, query_service=query_service, state_history_service=state_history_service
    )

    result = consistency_service.validate(task.task_id)

    assert all(violation.category != MISSING_REFERENCE for violation in result.violations)


def test_missing_context_reference_is_flagged():
    lifecycle_service, emitter, _ = _services()
    task = _create_task(lifecycle_service)
    event = emitter.emit(task.task_id, CONTEXT_UPDATED)

    query_service = LLMAgentTaskEventQueryService(store=emitter.store)
    context_service = LLMAgentTaskContextService()  # no context ever created for this task
    consistency_service = LLMAgentTaskEventConsistencyService(
        lifecycle_service, query_service=query_service, context_service=context_service
    )

    result = consistency_service.validate(task.task_id)

    assert any(
        violation.category == MISSING_REFERENCE and violation.event_id == event.event_id
        for violation in result.violations
    )


def test_missing_retry_schedule_reference_is_flagged():
    lifecycle_service, emitter, _ = _services()
    task = _create_task(lifecycle_service)
    event = emitter.emit(task.task_id, "retry_scheduled")

    query_service = LLMAgentTaskEventQueryService(store=emitter.store)
    # get_retry_schedule() only ever reads its own store -- eligibility_service is
    # never consulted by it, so a bare placeholder is enough here.
    retry_scheduler = LLMAgentTaskRetryScheduler(eligibility_service=object())
    consistency_service = LLMAgentTaskEventConsistencyService(
        lifecycle_service, query_service=query_service, retry_scheduler=retry_scheduler
    )

    result = consistency_service.validate(task.task_id)

    assert any(
        violation.category == MISSING_REFERENCE and violation.event_id == event.event_id
        for violation in result.violations
    )


def test_reference_checks_are_skipped_without_optional_collaborators():
    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    emitter.emit(task.task_id, CONTEXT_UPDATED)
    emitter.emit(task.task_id, "retry_scheduled")

    result = consistency_service.validate(task.task_id)

    assert all(violation.category != MISSING_REFERENCE for violation in result.violations)


# --- authoritative-state mismatch ---------------------------------------------------------------


def test_authoritative_state_mismatch_is_flagged():
    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    # authoritative lifecycle stays CREATED, but the event stream claims otherwise
    event = emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    result = consistency_service.validate(task.task_id)

    mismatches = [violation for violation in result.violations if violation.category == STATE_MISMATCH]
    assert len(mismatches) == 1
    assert mismatches[0].event_id == event.event_id


def test_authoritative_state_agreement_is_not_flagged():
    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    lifecycle_service.transition(task.task_id, PLANNED)

    result = consistency_service.validate(task.task_id)

    assert all(violation.category != STATE_MISMATCH for violation in result.violations)


# --- invalid event relationship -------------------------------------------------------------------


def test_missing_parent_reference_is_flagged():
    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    event = emitter.emit(task.task_id, CONTEXT_UPDATED, parent_event_id="does-not-exist")

    result = consistency_service.validate(task.task_id)

    assert any(
        violation.category == INVALID_RELATIONSHIP and violation.event_id == event.event_id
        for violation in result.violations
    )


def test_self_referential_parent_is_flagged():
    from backend.agent_task_events.models import AgentTaskEvent

    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    self_referencing = AgentTaskEvent(
        task_id=task.task_id, event_type=CONTEXT_UPDATED, event_id="self-ref", parent_event_id="self-ref"
    )
    emitter.store.save(self_referencing)

    result = consistency_service.validate(task.task_id)

    assert any(
        violation.category == INVALID_RELATIONSHIP and violation.event_id == "self-ref"
        for violation in result.violations
    )


def test_parent_occurring_after_child_is_flagged():
    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    child = emitter.emit(task.task_id, CONTEXT_UPDATED)
    parent = emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    from dataclasses import replace

    corrected_child = replace(child, parent_event_id=parent.event_id)
    emitter.store.save(corrected_child)

    result = consistency_service.validate(task.task_id)

    assert any(
        violation.category == INVALID_RELATIONSHIP and violation.event_id == corrected_child.event_id
        for violation in result.violations
    )


def test_correlation_mismatch_between_parent_and_child_is_flagged():
    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    parent = emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, correlation_id="corr-a")
    child = emitter.emit(task.task_id, CONTEXT_UPDATED, parent_event_id=parent.event_id, correlation_id="corr-b")

    result = consistency_service.validate(task.task_id)

    assert any(
        violation.category == INVALID_RELATIONSHIP and violation.event_id == child.event_id
        for violation in result.violations
    )


def test_valid_parent_child_relationship_is_not_flagged():
    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    parent = emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, correlation_id="corr-a")
    emitter.emit(task.task_id, CONTEXT_UPDATED, parent_event_id=parent.event_id, correlation_id="corr-a")

    result = consistency_service.validate(task.task_id)

    assert all(violation.category != INVALID_RELATIONSHIP for violation in result.violations)


def test_cross_task_parent_reference_is_valid():
    lifecycle_service, emitter, consistency_service = _services()
    task_a = _create_task(lifecycle_service)
    task_b = lifecycle_service.create(_definition())
    parent = emitter.emit(task_a.task_id, LIFECYCLE_TRANSITIONED)
    emitter.emit(task_b.task_id, CONTEXT_UPDATED, parent_event_id=parent.event_id)

    result = consistency_service.validate(task_b.task_id)

    assert all(violation.category != INVALID_RELATIONSHIP for violation in result.violations)


# --- valid legacy/uncorrelated events ---------------------------------------------------------------


def test_legacy_events_without_optional_metadata_are_valid():
    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED)  # no payload at all
    emitter.emit(task.task_id, "dependency_added")  # no correlation metadata

    result = consistency_service.validate(task.task_id)

    assert result.is_consistent is True
    assert result.violations == ()


# --- determinism -----------------------------------------------------------------------------------


def test_validate_is_deterministic_across_calls():
    lifecycle_service, emitter, consistency_service = _services()
    task = _create_task(lifecycle_service)
    emitter.emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": RUNNING})

    first = consistency_service.validate(task.task_id)
    second = consistency_service.validate(task.task_id)

    assert first == second
