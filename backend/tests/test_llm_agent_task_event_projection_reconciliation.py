import pytest

from backend.agent_task_events import (
    DEPENDENCY_ADDED,
    InMemoryAgentTaskEventStore,
    InvalidAgentTaskProjectionReconciliationError,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventProjectionReconciliationService,
    LLMAgentTaskEventProjectionService,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
)
from backend.agent_task_lifecycle import PLANNED, READY


def _services():
    event_store = InMemoryAgentTaskEventStore()
    emitter = LLMAgentTaskEventService(store=event_store)
    query_service = LLMAgentTaskEventQueryService(store=event_store)
    projection_service = LLMAgentTaskEventProjectionService(query_service=query_service)
    reconciliation_service = LLMAgentTaskEventProjectionReconciliationService(projection_service)
    return emitter, projection_service, reconciliation_service


# --- current projection --------------------------------------------------------------------


def test_check_reports_current_when_stored_matches_fresh_projection():
    emitter, projection_service, reconciliation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    projection_service.refresh("task-1")

    result = reconciliation_service.check("task-1")

    assert result.is_current is True
    assert result.differences == ()
    assert result.reconciled is False
    # equal in every content field; evaluated_at is pure bookkeeping and is
    # expected to differ between the stored projection and a fresh recompute
    assert result.stored_projection.current_state == result.expected_projection.current_state
    assert result.stored_projection.event_count == result.expected_projection.event_count


def test_check_ignores_bookkeeping_timestamp_differences():
    emitter, projection_service, reconciliation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    projection_service.refresh("task-1")

    # a second, later check() call recomputes expected_projection fresh (new
    # evaluated_at) even though nothing about the event stream changed
    result = reconciliation_service.check("task-1")

    assert result.is_current is True


def test_check_rejects_blank_task_id():
    _, _, reconciliation_service = _services()

    with pytest.raises(InvalidAgentTaskProjectionReconciliationError):
        reconciliation_service.check("")


# --- missing projection -----------------------------------------------------------------------


def test_check_reports_missing_projection():
    emitter, _, reconciliation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    result = reconciliation_service.check("task-1")

    assert result.is_current is False
    assert result.stored_projection is None
    assert len(result.differences) == 1
    assert result.differences[0].field == "projection"


def test_check_handles_missing_projection_for_empty_event_stream_cleanly():
    _, _, reconciliation_service = _services()

    result = reconciliation_service.check("task-1")

    assert result.is_current is False
    assert result.stored_projection is None
    assert result.expected_projection.event_count == 0


# --- stale projection / event-count mismatch ---------------------------------------------------


def test_check_detects_event_count_mismatch():
    emitter, projection_service, reconciliation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    projection_service.refresh("task-1")
    emitter.emit("task-1", DEPENDENCY_ADDED)  # advances the stream after refresh()

    result = reconciliation_service.check("task-1")

    assert result.is_current is False
    fields = {difference.field for difference in result.differences}
    assert "event_count" in fields


def test_check_detects_last_event_reference_staleness():
    emitter, projection_service, reconciliation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    projection_service.refresh("task-1")
    new_event = emitter.emit("task-1", DEPENDENCY_ADDED)

    result = reconciliation_service.check("task-1")

    fields = {difference.field for difference in result.differences}
    assert "last_event_id" in fields
    assert "last_event_at" in fields
    matching = [d for d in result.differences if d.field == "last_event_id"]
    assert matching[0].expected == new_event.event_id


# --- state mismatch ---------------------------------------------------------------------------


def test_check_detects_derived_state_mismatch():
    emitter, projection_service, reconciliation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    projection_service.refresh("task-1")
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})

    result = reconciliation_service.check("task-1")

    fields = {difference.field for difference in result.differences}
    assert "current_state" in fields
    matching = [d for d in result.differences if d.field == "current_state"][0]
    assert matching.stored == PLANNED
    assert matching.expected == READY


def test_check_detects_retry_reference_staleness():
    emitter, projection_service, reconciliation_service = _services()
    emitter.emit("task-1", "retry_scheduled")
    projection_service.refresh("task-1")
    emitter.emit("task-1", "retry_cancelled")

    result = reconciliation_service.check("task-1")

    fields = {difference.field for difference in result.differences}
    assert "active_retry_reference" in fields


# --- successful reconciliation ------------------------------------------------------------------


def test_reconcile_persists_fresh_projection_when_stale():
    emitter, projection_service, reconciliation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    projection_service.refresh("task-1")
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})

    result = reconciliation_service.reconcile("task-1")

    assert result.reconciled is True
    assert result.is_current is False  # reflects the state check() found, before the fix
    assert len(result.differences) > 0  # differences are not silently discarded

    after = projection_service.get("task-1")
    assert after.current_state == READY
    assert after.event_count == 2


def test_reconcile_persists_projection_for_previously_missing_one():
    emitter, projection_service, reconciliation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    result = reconciliation_service.reconcile("task-1")

    assert result.reconciled is True
    assert projection_service.get("task-1") is not None
    assert projection_service.get("task-1").current_state == PLANNED


def test_reconcile_is_a_no_op_when_already_current():
    emitter, projection_service, reconciliation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    projection_service.refresh("task-1")

    result = reconciliation_service.reconcile("task-1")

    assert result.reconciled is False
    assert result.is_current is True


# --- repeated reconciliation is idempotent -------------------------------------------------------


def test_repeated_reconciliation_is_idempotent():
    emitter, projection_service, reconciliation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    first = reconciliation_service.reconcile("task-1")
    second = reconciliation_service.reconcile("task-1")

    assert first.reconciled is True
    assert second.reconciled is False
    assert second.is_current is True

    stored_after_first = projection_service.get("task-1")
    stored_after_second = projection_service.get("task-1")
    assert stored_after_first.current_state == stored_after_second.current_state
    assert stored_after_first.event_count == stored_after_second.event_count


def test_reconcile_rejects_blank_task_id():
    _, _, reconciliation_service = _services()

    with pytest.raises(InvalidAgentTaskProjectionReconciliationError):
        reconciliation_service.reconcile("")


# --- authoritative task state is never modified ---------------------------------------------------


def test_reconciliation_never_mutates_stored_events():
    emitter, _, reconciliation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    before = emitter.get("task-1")
    reconciliation_service.check("task-1")
    reconciliation_service.reconcile("task-1")
    reconciliation_service.reconcile("task-1")
    after = emitter.get("task-1")

    assert before == after
    assert len(after) == 1


def test_reconciliation_service_has_no_lifecycle_mutation_methods():
    _, _, reconciliation_service = _services()

    assert not hasattr(reconciliation_service, "emit")
    assert not hasattr(reconciliation_service, "transition")
