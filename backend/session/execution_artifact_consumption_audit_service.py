from datetime import (
    datetime,
)

from threading import (
    RLock,
)

from .execution_artifact_consumption_audit_error import (
    ExecutionArtifactConsumptionAuditError,
)

from .execution_artifact_consumption_audit_event import (
    ExecutionArtifactConsumptionAuditEvent,
)


class ExecutionArtifactConsumptionAuditService:
    """
    Maintains an append-only audit trail of artifact consumption
    events, kept for debugging and compliance.

    The service's responsibility is audit bookkeeping only. It does
    not decide when a consumption event happens or what version an
    artifact is at; a caller builds a fully-formed
    ExecutionArtifactConsumptionAuditEvent, typically from an
    execution artifact consumption service and execution artifact
    consumption provenance service, and record()s it here.

    Behavior:
    - record() is append-only: a caller cannot edit or remove an
      event once recorded, and recording the same event ID twice is
      rejected as a duplicate
    - history(), artifact_history(), and latest() all return events
      in chronological (recorded_at) order, regardless of the order
      they were record()ed in
    - purge() is the sole exception to append-only: it permanently
      removes every event recorded before a given, caller-chosen
      cutoff, giving retention a configurable boundary rather than a
      fixed policy

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._events_by_id = {}
        self._event_ids_by_consumption = {}
        self._event_ids_by_artifact = {}
        self._event_ids_in_order = []
        self._lock = RLock()

    def record(self, event: ExecutionArtifactConsumptionAuditEvent) -> ExecutionArtifactConsumptionAuditEvent:
        """
        Append a new audit event.

        Raises:
            ExecutionArtifactConsumptionAuditError: If event is not
                an ExecutionArtifactConsumptionAuditEvent, or its
                event ID is already recorded
        """

        if not isinstance(event, ExecutionArtifactConsumptionAuditEvent):
            raise ExecutionArtifactConsumptionAuditError(
                "Cannot record an invalid event: event must be an ExecutionArtifactConsumptionAuditEvent."
            )

        with self._lock:
            if event.event_id in self._events_by_id:
                raise ExecutionArtifactConsumptionAuditError(
                    f"Event ID {event.event_id!r} is already recorded."
                )

            self._events_by_id[event.event_id] = event
            self._event_ids_by_consumption.setdefault(event.consumption_id, []).append(event.event_id)
            self._event_ids_by_artifact.setdefault(event.artifact_id, []).append(event.event_id)
            self._event_ids_in_order.append(event.event_id)

            return event

    def history(self, consumption_id: str) -> list:
        """
        List every recorded event for a consumption session, oldest
        to newest.

        Raises:
            ExecutionArtifactConsumptionAuditError: If consumption_id
                is None or blank
        """

        self._validate_id(consumption_id, "consumption ID")

        with self._lock:
            events = [
                self._events_by_id[event_id]
                for event_id in self._event_ids_by_consumption.get(consumption_id, [])
            ]

            return sorted(events, key=lambda event: event.recorded_at)

    def artifact_history(self, artifact_id: str) -> list:
        """
        List every recorded event for an artifact, across every
        consumption session, oldest to newest.

        Raises:
            ExecutionArtifactConsumptionAuditError: If artifact_id is
                None or blank
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            events = [
                self._events_by_id[event_id]
                for event_id in self._event_ids_by_artifact.get(artifact_id, [])
            ]

            return sorted(events, key=lambda event: event.recorded_at)

    def latest(self, consumption_id: str) -> ExecutionArtifactConsumptionAuditEvent:
        """
        Look up a consumption session's most recent event.

        Raises:
            ExecutionArtifactConsumptionAuditError: If consumption_id
                is None or blank, or it has no recorded events
        """

        self._validate_id(consumption_id, "consumption ID")

        history = self.history(consumption_id)

        if not history:
            raise ExecutionArtifactConsumptionAuditError(
                f"Consumption ID {consumption_id!r} has no recorded events."
            )

        return history[-1]

    def purge(self, before_timestamp: datetime) -> list:
        """
        Permanently remove every event recorded strictly before a
        cutoff.

        Raises:
            ExecutionArtifactConsumptionAuditError: If before_timestamp
                is not a datetime
        """

        if not isinstance(before_timestamp, datetime):
            raise ExecutionArtifactConsumptionAuditError("Cannot purge with a non-datetime before_timestamp.")

        with self._lock:
            purged_ids = [
                event_id
                for event_id in self._event_ids_in_order
                if self._events_by_id[event_id].recorded_at < before_timestamp
            ]

            purged = []

            for event_id in purged_ids:
                event = self._events_by_id.pop(event_id)

                self._event_ids_by_consumption[event.consumption_id].remove(event_id)
                self._event_ids_by_artifact[event.artifact_id].remove(event_id)
                self._event_ids_in_order.remove(event_id)

                purged.append(event)

            return sorted(purged, key=lambda event: event.recorded_at)

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionAuditError(f"Cannot use an empty or blank {field_name}.")
