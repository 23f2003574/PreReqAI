from threading import (
    RLock,
)

from .execution_observability_event import (
    ExecutionObservabilityEvent,
)

from .execution_observability_event_error import (
    ExecutionObservabilityEventError,
)


class ExecutionEventService:
    """
    Records structured lifecycle and operational events for execution
    tracing, kept isolated per runtime.

    Composes with an existing runtime service (anything exposing
    `status(runtime_id) -> str`, matching
    ExecutionRuntimeStartupService), used to confirm a runtime exists
    before an event can be recorded against it.

    Behavior:
    - record() is append-only: no method updates or removes an event
      once recorded; every occurrence is preserved in the order it
      was recorded
    - history() reports every event recorded for a runtime, oldest to
      newest
    - filter() reports a runtime's recorded events of a given
      event_type, oldest to newest
    - latest() reports a runtime's most recently recorded event, or
      None if it has never recorded one
    - An event recorded against one runtime never appears in another
      runtime's history(), filter(), or latest()

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, runtime_service):
        self._runtime_service = runtime_service
        self._events_by_runtime = {}
        self._lock = RLock()

    def record(
        self, runtime_id: str, event_type: str, severity: str, payload: object
    ) -> ExecutionObservabilityEvent:
        """
        Record a new event occurrence for runtime_id.

        Raises:
            ExecutionObservabilityEventError: If runtime_id or
                event_type is None or blank, severity is not one of
                SEVERITIES, or runtime_id is unknown
        """

        self._validate_text(runtime_id, "runtime ID")
        self._confirm_runtime_exists(runtime_id)

        event = ExecutionObservabilityEvent(
            runtime_id=runtime_id,
            event_type=event_type,
            severity=severity,
            payload=payload,
        )

        with self._lock:
            self._events_by_runtime.setdefault(runtime_id, []).append(event)

            return event

    def history(self, runtime_id: str) -> tuple:
        """
        Every event recorded for runtime_id, oldest to newest.

        Raises:
            ExecutionObservabilityEventError: If runtime_id is None
                or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            recorded = list(self._events_by_runtime.get(runtime_id, []))

        return tuple(sorted(recorded, key=lambda event: event.occurred_at))

    def filter(self, runtime_id: str, event_type: str) -> tuple:
        """
        runtime_id's recorded events of a given event_type, oldest to
        newest.

        Raises:
            ExecutionObservabilityEventError: If runtime_id or
                event_type is None or blank
        """

        self._validate_text(event_type, "event type")

        return tuple(event for event in self.history(runtime_id) if event.event_type == event_type)

    def latest(self, runtime_id: str):
        """
        The most recently recorded event for runtime_id, or None if
        it has never recorded one.

        Raises:
            ExecutionObservabilityEventError: If runtime_id is None
                or blank
        """

        events = self.history(runtime_id)

        return events[-1] if events else None

    def _confirm_runtime_exists(self, runtime_id: str) -> None:
        try:
            self._runtime_service.status(runtime_id)
        except Exception as error:
            raise ExecutionObservabilityEventError(
                f"Cannot record an event for runtime ID {runtime_id!r}: it is unknown."
            ) from error

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityEventError(f"Cannot use an empty or blank {field_name}.")
