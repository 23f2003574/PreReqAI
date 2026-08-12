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

from .execution_secret_lease import (
    ExecutionSecretLease,
)

from .execution_secret_lease_error import (
    ExecutionSecretLeaseError,
)

from .execution_secret_operation import (
    ExecutionSecretOperation,
)

_DEFAULT_TTL = timedelta(minutes=15)


class ExecutionSecretLeaseService:
    """
    Grants execution components temporary access to a secret, using
    an existing execution secret access service to confirm a
    principal is authorized to read a secret before a lease on it is
    acquired.

    The service's responsibility is lease bookkeeping only. It does
    not resolve or store raw secret values, and it enforces no access
    anywhere itself; a caller is expected to treat a non-ACTIVE lease
    as access ended.

    Behavior:
    - acquire() requires the access policy service to currently
      authorize the principal to READ the secret
    - A secret/principal pair may have at most one effectively active
      lease at a time; acquiring one already actively leased is
      rejected, but a lease that has expired or been released may be
      acquired again
    - A lease past its expires_at is effectively expired even before
      cleanup() records that in its status; renew() and release()
      both treat it as no longer ACTIVE, and it is excluded from
      active()
    - renew() extends an ACTIVE lease's expires_at; release() ends an
      ACTIVE lease's access immediately by marking it RELEASED
    - cleanup() marks every effectively expired ACTIVE lease EXPIRED

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_secret_access_service, ttl: timedelta = _DEFAULT_TTL):
        """
        Args:
            execution_secret_access_service: The service used to
                confirm a principal is currently authorized to READ a
                secret before a lease on it is acquired. Any object
                exposing `authorize(secret_id, principal, operation)`
                is accepted
            ttl: How long a newly acquired or renewed lease stays
                active before it expires
        """

        if not isinstance(ttl, timedelta):
            raise ExecutionSecretLeaseError("Cannot use a non-timedelta ttl.")

        self._execution_secret_access_service = execution_secret_access_service
        self._ttl = ttl
        self._leases_by_id = {}
        self._lease_id_by_key = {}
        self._lease_ids_in_order = []
        self._lease_ids_by_secret = {}
        self._lock = RLock()

    def acquire(self, secret_id: str, principal: str) -> ExecutionSecretLease:
        """
        Acquire a lease granting a principal temporary access to a
        secret.

        Raises:
            ExecutionSecretLeaseError: If secret_id or principal is
                None or blank, the access policy service does not
                currently authorize principal to READ secret_id, or
                the secret/principal pair already has an effectively
                active lease
        """

        self._validate_id(secret_id, "secret ID")
        self._validate_id(principal, "principal")

        self._ensure_authorized(secret_id, principal)

        with self._lock:
            key = (secret_id, principal)
            existing_id = self._lease_id_by_key.get(key)

            if existing_id is not None and self._effective_status(self._leases_by_id[existing_id]) == "ACTIVE":
                raise ExecutionSecretLeaseError(
                    f"Principal {principal!r} already has an active lease on secret ID {secret_id!r}."
                )

            lease_id = str(uuid4())

            lease = ExecutionSecretLease(
                lease_id=lease_id,
                secret_id=secret_id,
                principal=principal,
                expires_at=datetime.now(timezone.utc) + self._ttl,
            )

            self._leases_by_id[lease_id] = lease
            self._lease_id_by_key[key] = lease_id
            self._lease_ids_in_order.append(lease_id)
            self._lease_ids_by_secret.setdefault(secret_id, []).append(lease_id)

            return lease

    def renew(self, lease_id: str) -> ExecutionSecretLease:
        """
        Extend an ACTIVE lease's expiry.

        Raises:
            ExecutionSecretLeaseError: If lease_id is None or blank,
                no lease is known under it, or it is not effectively
                ACTIVE
        """

        self._validate_id(lease_id, "lease ID")

        with self._lock:
            lease = self._resolve(lease_id)

            self._ensure_effectively_active(lease)

            updated = replace(lease, expires_at=datetime.now(timezone.utc) + self._ttl)
            self._leases_by_id[lease_id] = updated

            return updated

    def release(self, lease_id: str) -> ExecutionSecretLease:
        """
        End an ACTIVE lease's access immediately.

        Raises:
            ExecutionSecretLeaseError: If lease_id is None or blank,
                no lease is known under it, or it is not effectively
                ACTIVE
        """

        self._validate_id(lease_id, "lease ID")

        with self._lock:
            lease = self._resolve(lease_id)

            self._ensure_effectively_active(lease)

            updated = replace(lease, status="RELEASED")
            self._leases_by_id[lease_id] = updated

            return updated

    def active(self, secret_id: str) -> list:
        """
        List a secret's effectively active leases, in the order they
        were acquired.

        Raises:
            ExecutionSecretLeaseError: If secret_id is None or blank
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            return [
                self._leases_by_id[lease_id]
                for lease_id in self._lease_ids_by_secret.get(secret_id, [])
                if self._effective_status(self._leases_by_id[lease_id]) == "ACTIVE"
            ]

    def expired(self) -> list:
        """
        List every ACTIVE lease that is currently past its expiry but
        has not yet been recorded EXPIRED by cleanup(), across every
        secret, in the order they were acquired.
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

    def _ensure_authorized(self, secret_id: str, principal: str) -> None:
        authorized = False

        try:
            authorized = self._execution_secret_access_service.authorize(
                secret_id, principal, ExecutionSecretOperation.READ
            )
        except Exception as error:
            raise ExecutionSecretLeaseError(
                f"Cannot acquire a lease for principal {principal!r} on secret ID {secret_id!r}: access policy "
                f"check failed."
            ) from error

        if not authorized:
            raise ExecutionSecretLeaseError(
                f"Principal {principal!r} is not authorized to READ secret ID {secret_id!r}."
            )

    def _ensure_effectively_active(self, lease: ExecutionSecretLease) -> None:
        if self._effective_status(lease) != "ACTIVE":
            raise ExecutionSecretLeaseError(f"Cannot modify lease ID {lease.lease_id!r}: it is not ACTIVE.")

    def _effective_status(self, lease: ExecutionSecretLease) -> str:
        if lease.status == "ACTIVE" and self._is_expired(lease):
            return "EXPIRED"

        return lease.status

    def _is_expired(self, lease: ExecutionSecretLease) -> bool:
        return lease.expires_at <= datetime.now(timezone.utc)

    def _resolve(self, lease_id: str) -> ExecutionSecretLease:
        lease = self._leases_by_id.get(lease_id)

        if lease is None:
            raise ExecutionSecretLeaseError(f"No lease is known under lease ID {lease_id!r}.")

        return lease

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionSecretLeaseError(f"Cannot use an empty or blank {field_name}.")
