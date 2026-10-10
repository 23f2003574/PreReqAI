from threading import (
    RLock,
)

from .execution_observation_event_error import (
    ExecutionObservationEventError,
)

from .execution_observation_event import (
    ExecutionObservationEvent,
)


class ExecutionObservationEventService:
    """
    Maintains an append-only log of execution observation events,
    the foundation for observability into workspace execution
    sessions.

    The service's responsibility is event bookkeeping only. It does
    not decide when an observation happens or what it means; a
    caller builds a fully-formed ExecutionObservationEvent and
    record()s it here. Execution sessions themselves are assumed to
    already exist and are never read or mutated by this service.

    Behavior:
    - record() is append-only: a caller cannot edit or remove an
      event once recorded, and recording the same event ID twice is
      rejected as a duplicate
    - history(), latest(), and filter() all return events in
      chronological (timestamp) order, regardless of the order they
      were record()ed in

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._events_by_id = {}
        self._event_ids_by_session = {}
        self._lock = RLock()

    def record(self, event: ExecutionObservationEvent) -> ExecutionObservationEvent:
        """
        Append a new observation event.

        Raises:
            ExecutionObservationEventError: If event is not an
                ExecutionObservationEvent, or its event ID is
                already recorded
        """

        if not isinstance(event, ExecutionObservationEvent):
            raise ExecutionObservationEventError(
                "Cannot record an invalid event: event must be an ExecutionObservationEvent."
            )

        with self._lock:
            if event.event_id in self._events_by_id:
                raise ExecutionObservationEventError(
                    f"Event ID {event.event_id!r} is already recorded."
                )

            self._events_by_id[event.event_id] = event
            self._event_ids_by_session.setdefault(event.session_id, []).append(event.event_id)

            return event

    def history(self, session_id: str) -> list:
        """
        List every recorded event for a session, oldest to newest.

        Raises:
            ExecutionObservationEventError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            events = [
                self._events_by_id[event_id]
                for event_id in self._event_ids_by_session.get(session_id, [])
            ]

            return sorted(events, key=lambda event: event.timestamp)

    def latest(self, session_id: str) -> ExecutionObservationEvent:
        """
        Look up a session's most recent event.

        Raises:
            ExecutionObservationEventError: If session_id is None or
                blank, or it has no recorded events
        """

        self._validate_id(session_id, "session ID")

        history = self.history(session_id)

        if not history:
            raise ExecutionObservationEventError(
                f"Session ID {session_id!r} has no recorded events."
            )

        return history[-1]

    def filter(self, session_id: str, event_type: str) -> list:
        """
        List a session's recorded events of one event_type, oldest
        to newest.

        Raises:
            ExecutionObservationEventError: If session_id or
                event_type is None or blank
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(event_type, "event type")

        return [
            event
            for event in self.history(session_id)
            if event.event_type == event_type
        ]

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationEventError(f"Cannot use an empty or blank {field_name}.")
