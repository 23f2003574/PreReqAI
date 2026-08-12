from threading import (
    RLock,
)

from .execution_secret_revocation import (
    ExecutionSecretRevocation,
)

from .execution_secret_revocation_error import (
    ExecutionSecretRevocationError,
)


class ExecutionSecretRevocationService:
    """
    Immediately invalidates a compromised or no-longer-required
    secret across active execution contexts, using an existing
    execution secret lease service to release every lease currently
    active on it.

    The service's responsibility is revocation bookkeeping and lease
    invalidation only. It does not resolve or store raw secret
    values, and it enforces nothing on its own beyond invalidating
    active leases; a caller is expected to check is_revoked() before
    granting any further access to a secret.

    Behavior:
    - revoke() releases every currently active lease on the secret,
      as part of the same call
    - A secret already revoked cannot be revoked again until it is
      restored
    - restore() requires an explicit authorized_by; it never happens
      implicitly
    - Revocation history is never rewritten or lost: restoring a
      secret clears its revoked status but leaves every past
      revocation record in history()

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_secret_lease_service):
        """
        Args:
            execution_secret_lease_service: The service used to
                release every lease active on a secret when it is
                revoked. Any object exposing `active(secret_id)`
                (returning an iterable of objects with a
                `.lease_id`) and `release(lease_id)` is accepted
        """

        self._execution_secret_lease_service = execution_secret_lease_service
        self._revocations_by_id = {}
        self._revocation_ids_by_secret = {}
        self._revoked_secret_ids = set()
        self._lock = RLock()

    def revoke(self, secret_id: str, reason: str, revoked_by: str = "system") -> ExecutionSecretRevocation:
        """
        Revoke a secret, immediately releasing every lease currently
        active on it.

        Raises:
            ExecutionSecretRevocationError: If secret_id, reason, or
                revoked_by is None or blank, or the secret is already
                revoked
        """

        self._validate_text(secret_id, "secret ID")
        self._validate_text(reason, "reason")
        self._validate_text(revoked_by, "revoked by")

        with self._lock:
            if secret_id in self._revoked_secret_ids:
                raise ExecutionSecretRevocationError(f"Secret ID {secret_id!r} is already revoked.")

            revocation = ExecutionSecretRevocation(
                secret_id=secret_id,
                reason=reason,
                revoked_by=revoked_by,
            )

            self._revocations_by_id[revocation.revocation_id] = revocation
            self._revocation_ids_by_secret.setdefault(secret_id, []).append(revocation.revocation_id)
            self._revoked_secret_ids.add(secret_id)

            for lease in self._execution_secret_lease_service.active(secret_id):
                self._execution_secret_lease_service.release(lease.lease_id)

            return revocation

    def is_revoked(self, secret_id: str) -> bool:
        """
        Check whether a secret is currently revoked.

        Raises:
            ExecutionSecretRevocationError: If secret_id is None or
                blank
        """

        self._validate_text(secret_id, "secret ID")

        with self._lock:
            return secret_id in self._revoked_secret_ids

    def history(self, secret_id: str) -> list:
        """
        List every revocation ever recorded for a secret, in the
        order they occurred.

        Raises:
            ExecutionSecretRevocationError: If secret_id is None or
                blank
        """

        self._validate_text(secret_id, "secret ID")

        with self._lock:
            return [
                self._revocations_by_id[revocation_id]
                for revocation_id in self._revocation_ids_by_secret.get(secret_id, [])
            ]

    def restore(self, secret_id: str, authorized_by: str) -> bool:
        """
        Restore a revoked secret, clearing its revoked status so it
        may be leased and revoked again.

        Raises:
            ExecutionSecretRevocationError: If secret_id or
                authorized_by is None or blank, or the secret is not
                currently revoked
        """

        self._validate_text(secret_id, "secret ID")
        self._validate_text(authorized_by, "authorized by")

        with self._lock:
            if secret_id not in self._revoked_secret_ids:
                raise ExecutionSecretRevocationError(f"Secret ID {secret_id!r} is not currently revoked.")

            self._revoked_secret_ids.discard(secret_id)

            return True

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretRevocationError(f"Cannot use an empty or blank {field_name}.")
