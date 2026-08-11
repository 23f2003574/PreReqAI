from threading import (
    RLock,
)

from .execution_observation_incident_transition_error import (
    ExecutionObservationIncidentTransitionError,
)

from .execution_observation_incident_transition import (
    ExecutionObservationIncidentTransition,
)

_ALLOWED_TRANSITIONS = {
    "OPEN": frozenset({"ACKNOWLEDGED"}),
    "ACKNOWLEDGED": frozenset({"ESCALATED", "RESOLVED"}),
    "ESCALATED": frozenset({"RESOLVED"}),
    "RESOLVED": frozenset(),
}


class ExecutionObservationIncidentLifecycleService:
    """
    Tracks an incident's lifecycle status, from OPEN through
    ACKNOWLEDGED to ESCALATED or RESOLVED. Observation incidents
    themselves are assumed to already exist; every incident_id
    implicitly starts OPEN in this service until acknowledge(),
    escalate(), or resolve() is called against it.

    Behavior:
    - Only OPEN -> ACKNOWLEDGED, ACKNOWLEDGED -> ESCALATED,
      ACKNOWLEDGED -> RESOLVED, and ESCALATED -> RESOLVED are valid
      transitions; any other call is rejected
    - RESOLVED is terminal: no further transition is ever accepted
      once an incident is RESOLVED
    - Every valid transition is recorded, append-only, and
      history() always returns them in chronological order

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._status_by_incident = {}
        self._history_by_incident = {}
        self._lock = RLock()

    def acknowledge(self, incident_id: str, actor: str) -> ExecutionObservationIncidentTransition:
        """
        Transition an OPEN incident to ACKNOWLEDGED.

        Raises:
            ExecutionObservationIncidentTransitionError: If
                incident_id or actor is None or blank, or the
                incident is not currently OPEN
        """

        return self._transition(incident_id, "ACKNOWLEDGED", actor)

    def escalate(self, incident_id: str, actor: str) -> ExecutionObservationIncidentTransition:
        """
        Transition an ACKNOWLEDGED incident to ESCALATED.

        Raises:
            ExecutionObservationIncidentTransitionError: If
                incident_id or actor is None or blank, or the
                incident is not currently ACKNOWLEDGED
        """

        return self._transition(incident_id, "ESCALATED", actor)

    def resolve(self, incident_id: str, actor: str) -> ExecutionObservationIncidentTransition:
        """
        Transition an ACKNOWLEDGED or ESCALATED incident to RESOLVED.

        Raises:
            ExecutionObservationIncidentTransitionError: If
                incident_id or actor is None or blank, or the
                incident is not currently ACKNOWLEDGED or ESCALATED
        """

        return self._transition(incident_id, "RESOLVED", actor)

    def history(self, incident_id: str) -> list:
        """
        List every transition recorded for an incident, oldest to
        newest.

        Raises:
            ExecutionObservationIncidentTransitionError: If
                incident_id is None or blank
        """

        self._validate_id(incident_id, "incident ID")

        with self._lock:
            return list(self._history_by_incident.get(incident_id, []))

    def status(self, incident_id: str) -> str:
        """
        Look up an incident's current lifecycle status, OPEN if no
        transition has been recorded for it yet.

        Raises:
            ExecutionObservationIncidentTransitionError: If
                incident_id is None or blank
        """

        self._validate_id(incident_id, "incident ID")

        with self._lock:
            return self._status_by_incident.get(incident_id, "OPEN")

    def _transition(self, incident_id: str, to_status: str, actor: str) -> ExecutionObservationIncidentTransition:
        self._validate_id(incident_id, "incident ID")
        self._validate_id(actor, "actor")

        with self._lock:
            current_status = self._status_by_incident.get(incident_id, "OPEN")

            if to_status not in _ALLOWED_TRANSITIONS[current_status]:
                raise ExecutionObservationIncidentTransitionError(
                    f"Cannot transition incident ID {incident_id!r} from {current_status} to {to_status}."
                )

            transition = ExecutionObservationIncidentTransition(
                incident_id=incident_id,
                from_status=current_status,
                to_status=to_status,
                actor=actor,
            )

            self._status_by_incident[incident_id] = to_status
            self._history_by_incident.setdefault(incident_id, []).append(transition)

            return transition

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationIncidentTransitionError(f"Cannot use an empty or blank {field_name}.")
