from threading import (
    RLock,
)

from .execution_observation_health_transition_error import (
    ExecutionObservationHealthTransitionError,
)

from .execution_observation_health_transition import (
    ExecutionObservationHealthTransition,
    SUPPORTED_STATUSES,
)


class ExecutionObservationHealthHistoryService:
    """
    Maintains an append-only log of a session's health status
    transitions, so operators can see when and why a session changed
    state. Health checks themselves are assumed to already exist; a
    caller record()s a transition each time a check's status differs
    from the session's previous status.

    Behavior:
    - record() ignores a call whose previous_status and
      current_status are the same, returning None without recording
      anything; no transition ever represents an unchanged status
    - record() is otherwise append-only: no method updates or
      removes a transition once recorded, and an explicitly given
      transition_id that is already recorded is rejected as a
      duplicate
    - history(), latest(), and transitions() all return transitions
      in chronological (timestamp) order, regardless of the order
      they were record()ed in
    - transitions() matches across every session, not just one

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._transitions_by_id = {}
        self._transition_ids_by_session = {}
        self._all_transition_ids = []
        self._lock = RLock()

    def record(
        self,
        session_id: str,
        previous_status: str,
        current_status: str,
        reasons=(),
        transition_id: str = None,
    ) -> ExecutionObservationHealthTransition:
        """
        Record a session's status changing from previous_status to
        current_status. A call where previous_status equals
        current_status is ignored.

        Args:
            transition_id: An optional caller-chosen identifier, for
                idempotent retries. When omitted, one is generated

        Raises:
            ExecutionObservationHealthTransitionError: If session_id
                is None or blank, previous_status or current_status
                is not a supported status, or transition_id is given
                and already recorded
        """

        self._validate_id(session_id, "session ID")

        if previous_status == current_status:
            return None

        with self._lock:
            kwargs = dict(
                session_id=session_id,
                previous_status=previous_status,
                current_status=current_status,
                reasons=tuple(reasons or ()),
            )

            if transition_id is not None:
                kwargs["transition_id"] = transition_id

            transition = ExecutionObservationHealthTransition(**kwargs)

            if transition.transition_id in self._transitions_by_id:
                raise ExecutionObservationHealthTransitionError(
                    f"Transition ID {transition.transition_id!r} is already recorded."
                )

            self._transitions_by_id[transition.transition_id] = transition
            self._transition_ids_by_session.setdefault(session_id, []).append(transition.transition_id)
            self._all_transition_ids.append(transition.transition_id)

            return transition

    def history(self, session_id: str) -> list:
        """
        List every recorded transition for a session, oldest to
        newest.

        Raises:
            ExecutionObservationHealthTransitionError: If session_id
                is None or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            transitions = [
                self._transitions_by_id[transition_id]
                for transition_id in self._transition_ids_by_session.get(session_id, [])
            ]

            return sorted(transitions, key=lambda transition: transition.timestamp)

    def latest(self, session_id: str) -> ExecutionObservationHealthTransition:
        """
        Look up a session's most recent transition.

        Raises:
            ExecutionObservationHealthTransitionError: If session_id
                is None or blank, or it has no recorded transitions
        """

        history = self.history(session_id)

        if not history:
            raise ExecutionObservationHealthTransitionError(
                f"Session ID {session_id!r} has no recorded transitions."
            )

        return history[-1]

    def transitions(self, from_status: str, to_status: str) -> list:
        """
        List every recorded transition, across every session, whose
        previous_status is from_status and current_status is
        to_status, oldest to newest.

        Raises:
            ExecutionObservationHealthTransitionError: If from_status
                or to_status is not a supported status
        """

        self._validate_status(from_status, "from status")
        self._validate_status(to_status, "to status")

        with self._lock:
            matching = [
                self._transitions_by_id[transition_id]
                for transition_id in self._all_transition_ids
                if self._transitions_by_id[transition_id].previous_status == from_status
                and self._transitions_by_id[transition_id].current_status == to_status
            ]

            return sorted(matching, key=lambda transition: transition.timestamp)

    def _validate_status(self, value: str, field_name: str) -> None:
        self._validate_id(value, field_name)

        if value not in SUPPORTED_STATUSES:
            raise ExecutionObservationHealthTransitionError(
                f"Unsupported {field_name} {value!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationHealthTransitionError(f"Cannot use an empty or blank {field_name}.")
