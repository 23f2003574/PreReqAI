from threading import (
    RLock,
)

from .execution_secret_audit_error import (
    ExecutionSecretAuditError,
)

from .execution_secret_audit_event import (
    ExecutionSecretAuditEvent,
)


class ExecutionSecretAuditService:
    """
    Records every security-sensitive operation performed against a
    secret, for traceability: access, rotation, lease, and revocation
    events alike.

    The service's responsibility is append-only bookkeeping. It does
    not perform, authorize, or interpret operations itself; a caller
    that performs one is expected to record() an event describing it.

    Behavior:
    - record() only ever appends: there is no way to remove or modify
      a recorded event, so history is never rewritten or lost
    - history(), session_history(), and principal_history() each
      return events in the order they were recorded
    - latest() returns a secret's most recently recorded event

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._events_by_id = {}
        self._event_ids_by_secret = {}
        self._event_ids_by_session = {}
        self._event_ids_by_principal = {}
        self._lock = RLock()

    def record(self, event: ExecutionSecretAuditEvent) -> ExecutionSecretAuditEvent:
        """
        Append an audit event.

        Raises:
            ExecutionSecretAuditError: If event is not an
                ExecutionSecretAuditEvent, or its event ID is already
                recorded
        """

        if not isinstance(event, ExecutionSecretAuditEvent):
            raise ExecutionSecretAuditError(
                "Cannot record an invalid event: event must be an ExecutionSecretAuditEvent."
            )

        with self._lock:
            if event.event_id in self._events_by_id:
                raise ExecutionSecretAuditError(f"Event ID {event.event_id!r} is already recorded.")

            self._events_by_id[event.event_id] = event
            self._event_ids_by_secret.setdefault(event.secret_id, []).append(event.event_id)
            self._event_ids_by_session.setdefault(event.session_id, []).append(event.event_id)
            self._event_ids_by_principal.setdefault(event.principal, []).append(event.event_id)

            return event

    def history(self, secret_id: str) -> list:
        """
        List every event recorded for a secret, in the order they
        were recorded.

        Raises:
            ExecutionSecretAuditError: If secret_id is None or blank
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            return self._events(self._event_ids_by_secret, secret_id)

    def session_history(self, session_id: str) -> list:
        """
        List every event recorded within a session, in the order they
        were recorded.

        Raises:
            ExecutionSecretAuditError: If session_id is None or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return self._events(self._event_ids_by_session, session_id)

    def principal_history(self, principal: str) -> list:
        """
        List every event recorded for a principal, in the order they
        were recorded.

        Raises:
            ExecutionSecretAuditError: If principal is None or blank
        """

        self._validate_id(principal, "principal")

        with self._lock:
            return self._events(self._event_ids_by_principal, principal)

    def latest(self, secret_id: str) -> ExecutionSecretAuditEvent:
        """
        Look up a secret's most recently recorded event.

        Raises:
            ExecutionSecretAuditError: If secret_id is None or blank,
                or no event has been recorded for it
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            event_ids = self._event_ids_by_secret.get(secret_id)

            if not event_ids:
                raise ExecutionSecretAuditError(f"No event is recorded for secret ID {secret_id!r}.")

            return self._events_by_id[event_ids[-1]]

    def _events(self, index: dict, key: str) -> list:
        return [self._events_by_id[event_id] for event_id in index.get(key, [])]

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretAuditError(f"Cannot use an empty or blank {field_name}.")
