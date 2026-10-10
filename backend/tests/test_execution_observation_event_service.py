from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionObservationEventError as Error,
    ExecutionObservationEvent,
    ExecutionObservationEventService,
)


def _event(
    session_id="session-1",
    event_type="STARTED",
    event_id=None,
    timestamp=None,
    metadata=None,
):
    kwargs = dict(
        session_id=session_id,
        event_type=event_type,
    )

    if event_id is not None:
        kwargs["event_id"] = event_id

    if timestamp is not None:
        kwargs["timestamp"] = timestamp

    if metadata is not None:
        kwargs["metadata"] = metadata

    return ExecutionObservationEvent(**kwargs)


class TestExecutionObservationEventService:
    def test_record_event(self):
        event_service = ExecutionObservationEventService()
        event = _event()

        recorded = event_service.record(event)

        assert recorded == event
        assert event_service.history("session-1") == [event]

    def test_history_ordering(self):
        event_service = ExecutionObservationEventService()
        base = datetime.now(timezone.utc)
        first = _event(event_id="event-1", event_type="STARTED", timestamp=base)
        second = _event(event_id="event-2", event_type="PROGRESSED", timestamp=base + timedelta(seconds=1))
        # Record out of chronological order to prove history() sorts by timestamp.
        event_service.record(second)
        event_service.record(first)

        history = event_service.history("session-1")

        assert [event.event_id for event in history] == ["event-1", "event-2"]

    def test_latest_event(self):
        event_service = ExecutionObservationEventService()
        base = datetime.now(timezone.utc)
        first = _event(event_id="event-1", timestamp=base)
        second = _event(event_id="event-2", timestamp=base + timedelta(seconds=1))
        event_service.record(first)
        event_service.record(second)

        assert event_service.latest("session-1") == second

        with pytest.raises(Error):
            event_service.latest("unknown-session")

    def test_event_filtering(self):
        event_service = ExecutionObservationEventService()
        base = datetime.now(timezone.utc)
        started = _event(event_id="event-1", event_type="STARTED", timestamp=base)
        progressed = _event(event_id="event-2", event_type="PROGRESSED", timestamp=base + timedelta(seconds=1))
        other_session = _event(event_id="event-3", session_id="session-2", event_type="STARTED", timestamp=base)
        event_service.record(started)
        event_service.record(progressed)
        event_service.record(other_session)

        filtered = event_service.filter("session-1", "STARTED")

        assert filtered == [started]

    def test_duplicate_id_rejection(self):
        event_service = ExecutionObservationEventService()
        event = _event(event_id="event-1")
        event_service.record(event)

        duplicate = _event(event_id="event-1", event_type="COMPLETED")

        with pytest.raises(Error):
            event_service.record(duplicate)

    def test_rejects_invalid_event(self):
        event_service = ExecutionObservationEventService()

        with pytest.raises(Error):
            event_service.record("not-an-event")

    def test_event_is_immutable(self):
        event_service = ExecutionObservationEventService()
        event = _event(metadata={"key": "value"})

        event_service.record(event)
        returned = event_service.history("session-1")[0]

        assert returned.metadata == {"key": "value"}
        with pytest.raises(Exception):
            returned.session_id = "session-2"
