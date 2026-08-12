from threading import (
    RLock,
)

from .execution_secret_anomaly import (
    ExecutionSecretAnomaly,
)

from .execution_secret_anomaly_error import (
    ExecutionSecretAnomalyError,
)

from .execution_secret_anomaly_type import (
    ExecutionSecretAnomalyType,
)

from .execution_secret_audit_operation import (
    ExecutionSecretAuditOperation,
)

_REPEATED_DENIAL_THRESHOLD = 3


class ExecutionSecretAnomalyService:
    """
    Detects suspicious secret access patterns across execution
    sessions and principals, by analyzing the record already kept by
    an existing execution secret audit service, lease service, and
    revocation service.

    The service's responsibility is detection and anomaly bookkeeping
    only. It never modifies secret, lease, or revocation state; it
    only reads from the services given at construction time.

    An ACCESS audit event is read as a single access attempt.
    Detection relies on two conventions callers are expected to
    record in an ACCESS event's metadata, since this service never
    performs access itself and so cannot observe attempts directly:
    - metadata["outcome"]: "granted" or "denied"
    - metadata["lease_id"]: the lease the attempt was made under, if
      any

    Behavior:
    - detect(secret_id) and detect_session(session_id) are safe to
      call repeatedly: each already-flagged piece of evidence (an
      event, or a principal's run of denials) is only ever flagged
      once, so repeated calls do not create duplicate anomalies
    - A secret with no revocation, no repeated denials, and no
      expired-lease access produces no anomalies

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        execution_secret_audit_service,
        execution_secret_lease_service,
        execution_secret_revocation_service,
    ):
        """
        Args:
            execution_secret_audit_service: The service read for a
                secret or session's recorded events. Any object
                exposing `history(secret_id)` and
                `session_history(session_id)` is accepted
            execution_secret_lease_service: The service read to tell
                whether a lease referenced by an ACCESS event is
                currently expired. Any object exposing `expired()`
                is accepted
            execution_secret_revocation_service: The service read to
                tell whether, and since when, a secret is currently
                revoked. Any object exposing `is_revoked(secret_id)`
                and `history(secret_id)` (returning objects with a
                `.revoked_at`) is accepted
        """

        self._execution_secret_audit_service = execution_secret_audit_service
        self._execution_secret_lease_service = execution_secret_lease_service
        self._execution_secret_revocation_service = execution_secret_revocation_service
        self._anomalies_by_id = {}
        self._anomaly_ids_in_order = []
        self._flagged_event_ids = set()
        self._flagged_denial_principals = set()
        self._lock = RLock()

    def detect(self, secret_id: str) -> list:
        """
        Detect anomalies for a secret from its recorded audit
        history.

        Raises:
            ExecutionSecretAnomalyError: If secret_id is None or
                blank
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            return self._detect_for_secret(secret_id)

    def detect_session(self, session_id: str) -> list:
        """
        Detect anomalies, across every secret referenced within a
        session's recorded audit history.

        Raises:
            ExecutionSecretAnomalyError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            secret_ids = []

            for event in self._execution_secret_audit_service.session_history(session_id):
                if event.secret_id not in secret_ids:
                    secret_ids.append(event.secret_id)

            detected = []

            for secret_id in secret_ids:
                detected.extend(self._detect_for_secret(secret_id))

            return detected

    def active(self) -> list:
        """
        List every unresolved anomaly, in the order it was detected.
        """

        with self._lock:
            return [self._anomalies_by_id[anomaly_id] for anomaly_id in self._anomaly_ids_in_order]

    def resolve(self, anomaly_id: str) -> ExecutionSecretAnomaly:
        """
        Resolve an anomaly, removing it from active().

        Raises:
            ExecutionSecretAnomalyError: If anomaly_id is None or
                blank, or no active anomaly is known under it
        """

        self._validate_id(anomaly_id, "anomaly ID")

        with self._lock:
            anomaly = self._anomalies_by_id.get(anomaly_id)

            if anomaly is None:
                raise ExecutionSecretAnomalyError(f"No active anomaly is known under anomaly ID {anomaly_id!r}.")

            del self._anomalies_by_id[anomaly_id]
            self._anomaly_ids_in_order.remove(anomaly_id)

            return anomaly

    def _detect_for_secret(self, secret_id: str) -> list:
        events = self._execution_secret_audit_service.history(secret_id)
        access_events = [event for event in events if event.operation == ExecutionSecretAuditOperation.ACCESS]

        detected = []

        detected.extend(self._detect_revoked_access(secret_id, access_events))
        detected.extend(self._detect_repeated_denial(secret_id, access_events))
        detected.extend(self._detect_expired_lease_access(secret_id, access_events))

        return detected

    def _detect_revoked_access(self, secret_id: str, access_events: list) -> list:
        if not self._execution_secret_revocation_service.is_revoked(secret_id):
            return []

        revocations = self._execution_secret_revocation_service.history(secret_id)

        if not revocations:
            return []

        revoked_at = revocations[-1].revoked_at

        detected = []

        for event in access_events:
            if event.event_id in self._flagged_event_ids:
                continue

            if event.timestamp <= revoked_at:
                continue

            self._flagged_event_ids.add(event.event_id)

            detected.append(
                self._record(
                    secret_id=secret_id,
                    principal=event.principal,
                    anomaly_type=ExecutionSecretAnomalyType.REVOKED_ACCESS,
                    details={"event_id": event.event_id, "revoked_at": revoked_at.isoformat()},
                )
            )

        return detected

    def _detect_repeated_denial(self, secret_id: str, access_events: list) -> list:
        denial_counts = {}

        for event in access_events:
            if event.metadata.get("outcome") == "denied":
                denial_counts[event.principal] = denial_counts.get(event.principal, 0) + 1

        detected = []

        for principal, count in denial_counts.items():
            key = (secret_id, principal)

            if count < _REPEATED_DENIAL_THRESHOLD or key in self._flagged_denial_principals:
                continue

            self._flagged_denial_principals.add(key)

            detected.append(
                self._record(
                    secret_id=secret_id,
                    principal=principal,
                    anomaly_type=ExecutionSecretAnomalyType.REPEATED_DENIAL,
                    details={"denied_count": count, "threshold": _REPEATED_DENIAL_THRESHOLD},
                )
            )

        return detected

    def _detect_expired_lease_access(self, secret_id: str, access_events: list) -> list:
        expired_lease_ids = {lease.lease_id for lease in self._execution_secret_lease_service.expired()}

        detected = []

        for event in access_events:
            lease_id = event.metadata.get("lease_id")

            if lease_id is None or lease_id not in expired_lease_ids:
                continue

            if event.event_id in self._flagged_event_ids:
                continue

            self._flagged_event_ids.add(event.event_id)

            detected.append(
                self._record(
                    secret_id=secret_id,
                    principal=event.principal,
                    anomaly_type=ExecutionSecretAnomalyType.EXPIRED_LEASE_ACCESS,
                    details={"event_id": event.event_id, "lease_id": lease_id},
                )
            )

        return detected

    def _record(self, secret_id: str, principal: str, anomaly_type: ExecutionSecretAnomalyType, details: dict) -> ExecutionSecretAnomaly:
        anomaly = ExecutionSecretAnomaly(
            secret_id=secret_id,
            principal=principal,
            anomaly_type=anomaly_type,
            details=details,
        )

        self._anomalies_by_id[anomaly.anomaly_id] = anomaly
        self._anomaly_ids_in_order.append(anomaly.anomaly_id)

        return anomaly

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretAnomalyError(f"Cannot use an empty or blank {field_name}.")
