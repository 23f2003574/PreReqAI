from threading import (
    RLock,
)

from .execution_policy_audit_error import (
    ExecutionPolicyAuditError,
)

from .execution_policy_audit_event import (
    ExecutionPolicyAuditEvent,
)


class ExecutionPolicyAuditService:
    """
    Records an append-only trail of every policy evaluation,
    conflict, exception, simulation, and enforcement decision.

    The service is a passive ledger only. It never calls into, and
    is never called by, the evaluation, conflict, exception,
    simulation, or enforcement services built by earlier commits;
    a caller who performs one of those operations is responsible for
    also calling record() with the resulting event. Recording an
    event never alters, retries, or reverses the operation it
    describes.

    Behavior:
    - record() is the only way an event enters the trail; there is
      no update or delete for an individual event, only purge()
    - history(), policy_history(), and latest() always return events
      in chronological order, by timestamp, regardless of the order
      record() was called in
    - purge() is the sole exception to append-only: it permanently
      forgets every event at or before a cutoff, across every index

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._events_by_id = {}
        self._event_ids_by_session = {}
        self._event_ids_by_policy = {}
        self._sequence = 0
        self._sequence_by_id = {}
        self._lock = RLock()

    def record(self, event: ExecutionPolicyAuditEvent) -> ExecutionPolicyAuditEvent:
        """
        Append an event to the trail.

        Raises:
            ExecutionPolicyAuditError: If event is not an
                ExecutionPolicyAuditEvent, or its event_id is already
                recorded
        """

        if not isinstance(event, ExecutionPolicyAuditEvent):
            raise ExecutionPolicyAuditError(
                "Cannot record an invalid event: event must be an ExecutionPolicyAuditEvent."
            )

        with self._lock:
            if event.event_id in self._events_by_id:
                raise ExecutionPolicyAuditError(f"Event ID {event.event_id!r} is already recorded.")

            self._events_by_id[event.event_id] = event
            self._sequence_by_id[event.event_id] = self._sequence
            self._sequence += 1

            self._event_ids_by_session.setdefault(event.session_id, []).append(event.event_id)

            for policy_id in event.policy_ids:
                self._event_ids_by_policy.setdefault(policy_id, []).append(event.event_id)

            return event

    def history(self, session_id: str) -> list:
        """
        List every event recorded for a session, in chronological
        order.

        Raises:
            ExecutionPolicyAuditError: If session_id is None or
                blank
        """

        self._validate_text(session_id, "session ID")

        with self._lock:
            return self._ordered(self._event_ids_by_session.get(session_id, []))

    def policy_history(self, policy_id: str) -> list:
        """
        List every event that concerns a policy, in chronological
        order.

        Raises:
            ExecutionPolicyAuditError: If policy_id is None or blank
        """

        self._validate_text(policy_id, "policy ID")

        with self._lock:
            return self._ordered(self._event_ids_by_policy.get(policy_id, []))

    def latest(self, session_id: str) -> ExecutionPolicyAuditEvent:
        """
        Look up the most recent event recorded for a session.

        Raises:
            ExecutionPolicyAuditError: If session_id is None or
                blank, or no event has been recorded for it
        """

        self._validate_text(session_id, "session ID")

        with self._lock:
            events = self._ordered(self._event_ids_by_session.get(session_id, []))

            if not events:
                raise ExecutionPolicyAuditError(f"No event has been recorded for session ID {session_id!r}.")

            return events[-1]

    def purge(self, before_timestamp) -> list:
        """
        Permanently remove every event at or before a cutoff
        timestamp, across every index.

        Raises:
            ExecutionPolicyAuditError: If before_timestamp is None
        """

        if before_timestamp is None:
            raise ExecutionPolicyAuditError("Cannot purge with a None before_timestamp.")

        with self._lock:
            purged_ids = [
                event_id
                for event_id, event in self._events_by_id.items()
                if event.timestamp <= before_timestamp
            ]

            purged = self._ordered(purged_ids)

            for event_id in purged_ids:
                event = self._events_by_id.pop(event_id)
                self._sequence_by_id.pop(event_id, None)

                session_ids = self._event_ids_by_session.get(event.session_id)
                if session_ids is not None:
                    session_ids.remove(event_id)
                    if not session_ids:
                        del self._event_ids_by_session[event.session_id]

                for policy_id in event.policy_ids:
                    policy_ids = self._event_ids_by_policy.get(policy_id)
                    if policy_ids is not None:
                        policy_ids.remove(event_id)
                        if not policy_ids:
                            del self._event_ids_by_policy[policy_id]

            return purged

    def _ordered(self, event_ids) -> list:
        return [
            self._events_by_id[event_id]
            for event_id in sorted(
                event_ids,
                key=lambda event_id: (self._events_by_id[event_id].timestamp, self._sequence_by_id[event_id]),
            )
        ]

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyAuditError(f"Cannot use an empty or blank {field_name}.")
