from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .execution_observation_incident_error import (
    ExecutionObservationIncidentError,
)

from .execution_observation_incident import (
    ExecutionObservationIncident,
)


class ExecutionObservationIncidentService:
    """
    Groups related observation events (errors, alerts, health
    transitions) into actionable execution incidents. Those
    observation events are assumed to already exist; a caller
    correlates one to an incident by passing its ID to open() or
    add().

    Behavior:
    - open() starts a new ACTIVE incident, correlating a starting
      set of event IDs
    - add() correlates one more event ID to an incident; the
      incident's event_ids preserves the order events were added in,
      starting with the order given to open()
    - Only an ACTIVE incident accepts events: add() and resolve()
      both reject an incident that has already resolved
    - resolve() records resolved_at and makes the incident
      permanently immutable
    - active() lists only a session's still-ACTIVE incidents;
      history() lists every incident, active or resolved

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._incidents_by_id = {}
        self._incident_ids_by_session = {}
        self._lock = RLock()

    def open(self, session_id: str, event_ids, severity: str = "MEDIUM") -> ExecutionObservationIncident:
        """
        Open a new ACTIVE incident for a session, correlating a
        starting set of event IDs.

        Raises:
            ExecutionObservationIncidentError: If session_id or
                severity is None or blank, or event_ids contains a
                blank or duplicate event ID
        """

        with self._lock:
            incident = ExecutionObservationIncident(session_id=session_id, severity=severity, event_ids=event_ids)

            self._incidents_by_id[incident.incident_id] = incident
            self._incident_ids_by_session.setdefault(session_id, []).append(incident.incident_id)

            return incident

    def add(self, incident_id: str, event_id: str) -> ExecutionObservationIncident:
        """
        Correlate one more event ID to an ACTIVE incident.

        Raises:
            ExecutionObservationIncidentError: If incident_id or
                event_id is None or blank, no incident is known
                under incident_id, it has already resolved, or the
                event ID is already correlated to it
        """

        self._validate_id(incident_id, "incident ID")
        self._validate_id(event_id, "event ID")

        with self._lock:
            incident = self._resolve(incident_id)

            self._ensure_active(incident)

            if event_id in incident.event_ids:
                raise ExecutionObservationIncidentError(
                    f"Event ID {event_id!r} is already correlated to incident ID {incident_id!r}."
                )

            updated = replace(incident, event_ids=incident.event_ids + (event_id,))
            self._incidents_by_id[incident_id] = updated

            return updated

    def resolve(self, incident_id: str) -> ExecutionObservationIncident:
        """
        Resolve an ACTIVE incident, recording resolved_at and making
        it immutable.

        Raises:
            ExecutionObservationIncidentError: If incident_id is
                None or blank, no incident is known under it, or it
                has already resolved
        """

        self._validate_id(incident_id, "incident ID")

        with self._lock:
            incident = self._resolve(incident_id)

            self._ensure_active(incident)

            updated = replace(incident, status="RESOLVED", resolved_at=datetime.now(timezone.utc))
            self._incidents_by_id[incident_id] = updated

            return updated

    def active(self, session_id: str) -> list:
        """
        List a session's still-ACTIVE incidents, in the order they
        were opened.

        Raises:
            ExecutionObservationIncidentError: If session_id is None
                or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return [
                self._incidents_by_id[incident_id]
                for incident_id in self._incident_ids_by_session.get(session_id, [])
                if self._incidents_by_id[incident_id].status == "ACTIVE"
            ]

    def history(self, session_id: str) -> list:
        """
        List every incident recorded for a session, active or
        resolved, in the order they were opened.

        Raises:
            ExecutionObservationIncidentError: If session_id is None
                or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return [
                self._incidents_by_id[incident_id]
                for incident_id in self._incident_ids_by_session.get(session_id, [])
            ]

    def _ensure_active(self, incident: ExecutionObservationIncident) -> None:
        if incident.status != "ACTIVE":
            raise ExecutionObservationIncidentError(
                f"Cannot modify incident ID {incident.incident_id!r}: it is {incident.status}, not ACTIVE."
            )

    def _resolve(self, incident_id: str) -> ExecutionObservationIncident:
        incident = self._incidents_by_id.get(incident_id)

        if incident is None:
            raise ExecutionObservationIncidentError(f"No incident is known under incident ID {incident_id!r}.")

        return incident

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationIncidentError(f"Cannot use an empty or blank {field_name}.")
