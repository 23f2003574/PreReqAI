from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_artifact_consumption_lease import (
    ExecutionArtifactConsumptionLease,
)

from .execution_artifact_consumption_lease_error import (
    ExecutionArtifactConsumptionLeaseError,
)

_DEFAULT_TTL = timedelta(minutes=15)


class ExecutionArtifactConsumptionLeaseService:
    """
    Keeps an artifact valid for consumption only while its consumer
    holds an active lease on it within an active consumption session,
    using an existing execution artifact consumption service to
    confirm both before a lease is acquired.

    The service's responsibility is lease bookkeeping only. It does
    not track consumption sessions or enforce access anywhere itself;
    a caller is expected to treat a non-ACTIVE lease as access ended.

    Behavior:
    - acquire() requires the consumption session to be ACTIVE and to
      currently track the artifact being leased
    - A consumption/artifact pair may have at most one effectively
      active lease at a time; acquiring one already actively leased
      is rejected, but a lease that has expired or been released may
      be acquired again
    - A lease past its expires_at is effectively expired even before
      cleanup() records that in its status; renew() and release()
      both treat it as no longer ACTIVE
    - renew() extends an ACTIVE lease's expires_at; release() ends an
      ACTIVE lease's access immediately by marking it RELEASED
    - cleanup() marks every effectively expired ACTIVE lease EXPIRED

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_consumption_service, ttl: timedelta = _DEFAULT_TTL):
        """
        Args:
            execution_artifact_consumption_service: The service used
                to confirm a consumption session is ACTIVE and tracks
                an artifact before a lease on it is acquired. Any
                object exposing `get(consumption_id)` (returning an
                object with `.status` and `.artifact_ids`), raising
                if the session is unknown, is accepted
            ttl: How long a newly acquired or renewed lease stays
                active before it expires
        """

        if not isinstance(ttl, timedelta):
            raise ExecutionArtifactConsumptionLeaseError("Cannot use a non-timedelta ttl.")

        self._execution_artifact_consumption_service = execution_artifact_consumption_service
        self._ttl = ttl
        self._leases_by_id = {}
        self._lease_id_by_key = {}
        self._lease_ids_in_order = []
        self._lock = RLock()

    def acquire(self, consumption_id: str, artifact_id: str) -> ExecutionArtifactConsumptionLease:
        """
        Acquire a lease on an artifact within an active consumption
        session.

        Raises:
            ExecutionArtifactConsumptionLeaseError: If consumption_id
                or artifact_id is None or blank, no consumption
                session is known under consumption_id, it is not
                ACTIVE, it does not currently track artifact_id, or
                the consumption/artifact pair already has an
                effectively active lease
        """

        self._validate_id(consumption_id, "consumption ID")
        self._validate_id(artifact_id, "artifact ID")

        self._ensure_active_consumption(consumption_id, artifact_id)

        with self._lock:
            key = (consumption_id, artifact_id)
            existing_id = self._lease_id_by_key.get(key)

            if existing_id is not None and self._effective_status(self._leases_by_id[existing_id]) == "ACTIVE":
                raise ExecutionArtifactConsumptionLeaseError(
                    f"Consumption ID {consumption_id!r} already has an active lease on artifact ID "
                    f"{artifact_id!r}."
                )

            lease_id = str(uuid4())

            lease = ExecutionArtifactConsumptionLease(
                lease_id=lease_id,
                consumption_id=consumption_id,
                artifact_id=artifact_id,
                expires_at=datetime.now(timezone.utc) + self._ttl,
            )

            self._leases_by_id[lease_id] = lease
            self._lease_id_by_key[key] = lease_id
            self._lease_ids_in_order.append(lease_id)

            return lease

    def renew(self, lease_id: str) -> ExecutionArtifactConsumptionLease:
        """
        Extend an ACTIVE lease's expiry.

        Raises:
            ExecutionArtifactConsumptionLeaseError: If lease_id is
                None or blank, no lease is known under it, or it is
                not effectively ACTIVE
        """

        self._validate_id(lease_id, "lease ID")

        with self._lock:
            lease = self._resolve(lease_id)

            self._ensure_effectively_active(lease)

            updated = replace(lease, expires_at=datetime.now(timezone.utc) + self._ttl)
            self._leases_by_id[lease_id] = updated

            return updated

    def release(self, lease_id: str) -> ExecutionArtifactConsumptionLease:
        """
        End an ACTIVE lease's access immediately.

        Raises:
            ExecutionArtifactConsumptionLeaseError: If lease_id is
                None or blank, no lease is known under it, or it is
                not effectively ACTIVE
        """

        self._validate_id(lease_id, "lease ID")

        with self._lock:
            lease = self._resolve(lease_id)

            self._ensure_effectively_active(lease)

            updated = replace(lease, status="RELEASED")
            self._leases_by_id[lease_id] = updated

            return updated

    def expired(self) -> list:
        """
        List every ACTIVE lease that is currently past its expiry but
        has not yet been recorded EXPIRED by cleanup(), in the order
        they were acquired.
        """

        with self._lock:
            return [
                self._leases_by_id[lease_id]
                for lease_id in self._lease_ids_in_order
                if self._leases_by_id[lease_id].status == "ACTIVE" and self._is_expired(self._leases_by_id[lease_id])
            ]

    def cleanup(self) -> list:
        """
        Record every currently expired ACTIVE lease as EXPIRED.

        Returns the leases that were transitioned, in the order they
        were acquired.
        """

        with self._lock:
            updated = []

            for lease_id in self._lease_ids_in_order:
                lease = self._leases_by_id[lease_id]

                if lease.status == "ACTIVE" and self._is_expired(lease):
                    new_lease = replace(lease, status="EXPIRED")
                    self._leases_by_id[lease_id] = new_lease
                    updated.append(new_lease)

            return updated

    def _ensure_active_consumption(self, consumption_id: str, artifact_id: str) -> None:
        try:
            session = self._execution_artifact_consumption_service.get(consumption_id)
        except Exception as error:
            raise ExecutionArtifactConsumptionLeaseError(
                f"No consumption session is known under consumption ID {consumption_id!r}."
            ) from error

        if session.status != "ACTIVE":
            raise ExecutionArtifactConsumptionLeaseError(
                f"Cannot lease under consumption ID {consumption_id!r}: it is {session.status}, not ACTIVE."
            )

        if artifact_id not in session.artifact_ids:
            raise ExecutionArtifactConsumptionLeaseError(
                f"Artifact ID {artifact_id!r} is not tracked by consumption ID {consumption_id!r}."
            )

    def _ensure_effectively_active(self, lease: ExecutionArtifactConsumptionLease) -> None:
        if self._effective_status(lease) != "ACTIVE":
            raise ExecutionArtifactConsumptionLeaseError(
                f"Cannot modify lease ID {lease.lease_id!r}: it is not ACTIVE."
            )

    def _effective_status(self, lease: ExecutionArtifactConsumptionLease) -> str:
        if lease.status == "ACTIVE" and self._is_expired(lease):
            return "EXPIRED"

        return lease.status

    def _is_expired(self, lease: ExecutionArtifactConsumptionLease) -> bool:
        return lease.expires_at <= datetime.now(timezone.utc)

    def _resolve(self, lease_id: str) -> ExecutionArtifactConsumptionLease:
        lease = self._leases_by_id.get(lease_id)

        if lease is None:
            raise ExecutionArtifactConsumptionLeaseError(f"No lease is known under lease ID {lease_id!r}.")

        return lease

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionLeaseError(f"Cannot use an empty or blank {field_name}.")
