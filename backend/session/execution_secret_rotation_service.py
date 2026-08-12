from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_secret_rotation import (
    ExecutionSecretRotation,
)

from .execution_secret_rotation_error import (
    ExecutionSecretRotationError,
)


class ExecutionSecretRotationService:
    """
    Rotates execution secrets to a fresh value_ref without
    interrupting active sessions: rotation only ever changes which
    reference is current, never the secret's identity, so a session
    already holding the secret_id keeps working through a rotation.

    The service's responsibility is rotation bookkeeping only. It
    does not resolve or store raw secret values itself; it relies on
    an existing execution secret registry only to confirm a secret is
    not currently expired before rotating it.

    Behavior:
    - rotate() generates a brand new current_ref and records the
      reference it replaces as previous_ref, kept only so a rollback
      can restore it
    - A secret's first rotation has no previous_ref: there is nothing
      earlier for this service to have tracked
    - current() and history() are scoped per secret_id and never see
      another secret's rotations
    - rollback() restores the previous_ref recorded on a specific
      rotation, and is itself recorded as a new rotation so history
      is never rewritten or lost
    - Expired secrets cannot be rotated or rolled back

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock, so a rotation's new reference becomes current atomically
    """

    def __init__(self, execution_secret_service):
        """
        Args:
            execution_secret_service: The registry used to confirm a
                secret is not currently expired before it is rotated
                or rolled back. Any object exposing `expired()`,
                returning an iterable of objects with a `.secret_id`,
                is accepted
        """

        self._execution_secret_service = execution_secret_service
        self._rotations_by_id = {}
        self._rotation_ids_by_secret = {}
        self._current_ref_by_secret = {}
        self._lock = RLock()

    def rotate(self, secret_id: str) -> ExecutionSecretRotation:
        """
        Rotate a secret to a fresh reference, which becomes current
        atomically.

        Raises:
            ExecutionSecretRotationError: If secret_id is None or
                blank, or the secret is currently expired
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            self._require_not_expired(secret_id)

            return self._apply(secret_id, current_ref=str(uuid4()))

    def current(self, secret_id: str) -> str:
        """
        Look up a secret's currently active reference.

        Raises:
            ExecutionSecretRotationError: If secret_id is None or
                blank, or the secret has never been rotated
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            current_ref = self._current_ref_by_secret.get(secret_id)

            if current_ref is None:
                raise ExecutionSecretRotationError(
                    f"Secret ID {secret_id!r} has never been rotated."
                )

            return current_ref

    def history(self, secret_id: str) -> list:
        """
        List a secret's rotations, in the order they occurred.

        Raises:
            ExecutionSecretRotationError: If secret_id is None or
                blank
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            return [
                self._rotations_by_id[rotation_id]
                for rotation_id in self._rotation_ids_by_secret.get(secret_id, [])
            ]

    def rollback(self, rotation_id: str) -> ExecutionSecretRotation:
        """
        Roll a secret back to the reference that was active
        immediately before a specific rotation, recording the
        rollback itself as a new rotation.

        Raises:
            ExecutionSecretRotationError: If rotation_id is None or
                blank, no rotation is recorded under it, it has no
                previous_ref to roll back to, or the secret is
                currently expired
        """

        self._validate_id(rotation_id, "rotation ID")

        with self._lock:
            rotation = self._resolve(rotation_id)

            if rotation.previous_ref is None:
                raise ExecutionSecretRotationError(
                    f"Rotation ID {rotation_id!r} has no previous reference to roll back to."
                )

            self._require_not_expired(rotation.secret_id)

            return self._apply(rotation.secret_id, current_ref=rotation.previous_ref)

    def _apply(self, secret_id: str, current_ref: str) -> ExecutionSecretRotation:
        rotation = ExecutionSecretRotation(
            rotation_id=str(uuid4()),
            secret_id=secret_id,
            previous_ref=self._current_ref_by_secret.get(secret_id),
            current_ref=current_ref,
            rotated_at=datetime.now(timezone.utc),
        )

        self._rotations_by_id[rotation.rotation_id] = rotation
        self._rotation_ids_by_secret.setdefault(secret_id, []).append(rotation.rotation_id)
        self._current_ref_by_secret[secret_id] = current_ref

        return rotation

    def _resolve(self, rotation_id: str) -> ExecutionSecretRotation:
        rotation = self._rotations_by_id.get(rotation_id)

        if rotation is None:
            raise ExecutionSecretRotationError(f"No rotation is recorded under rotation ID {rotation_id!r}.")

        return rotation

    def _require_not_expired(self, secret_id: str) -> None:
        for secret in self._execution_secret_service.expired():
            if secret.secret_id == secret_id:
                raise ExecutionSecretRotationError(
                    f"Cannot rotate secret ID {secret_id!r}: it is currently expired."
                )

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretRotationError(f"Cannot use an empty or blank {field_name}.")
