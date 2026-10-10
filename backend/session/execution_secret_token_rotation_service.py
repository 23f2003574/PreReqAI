from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_secret_operation import (
    ExecutionSecretOperation,
)

from .execution_secret_token_rotation import (
    ExecutionSecretTokenRotation,
)

from .execution_secret_token_rotation_error import (
    ExecutionSecretTokenRotationError,
)


class ExecutionSecretTokenRotationService:
    """
    Rotates a principal's execution secret access token to a freshly
    issued token, without invalidating any unrelated active token:
    another principal's token on the same secret, or the same
    principal's token on a different secret, is never touched by a
    rotation.

    The service's responsibility is rotation bookkeeping only. It
    does not issue or revoke tokens itself; it relies on an existing
    execution secret token service for both, and on an existing
    execution secret access policy service to confirm a principal is
    authorized to ROTATE a secret before doing so.

    Behavior:
    - rotate() requires the access policy service to currently
      authorize the principal to ROTATE the secret
    - rotate() issues a fresh token through the token service and
      records the token it replaces as previous_token_id, but leaves
      that previous token itself untouched: it stays whatever the
      token service already considers it to be, valid or not, until
      revoke_previous() is called for this rotation
    - A principal's first rotation for a secret has no
      previous_token_id: there is nothing earlier to record
    - current() and history() are scoped per secret_id; current() is
      further scoped per principal, since a secret may have many
      principals each rotating their own token independently

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock, so a rotation's new token becomes current atomically
    """

    def __init__(self, execution_secret_token_service, execution_secret_access_service):
        """
        Args:
            execution_secret_token_service: The service used to issue
                a fresh token on rotate() and revoke a rotation's
                previous token on revoke_previous(). Any object
                exposing `issue(secret_id, principal)` and
                `revoke(token_id)` is accepted
            execution_secret_access_service: The service used to
                confirm a principal is currently authorized to ROTATE
                a secret before rotate() proceeds. Any object exposing
                `authorize(secret_id, principal, operation)` is
                accepted
        """

        self._execution_secret_token_service = execution_secret_token_service
        self._execution_secret_access_service = execution_secret_access_service
        self._rotations_by_id = {}
        self._rotation_ids_by_secret = {}
        self._current_token_id_by_key = {}
        self._lock = RLock()

    def rotate(self, secret_id: str, principal: str) -> ExecutionSecretTokenRotation:
        """
        Rotate a principal's token for a secret to a freshly issued
        one, which becomes current atomically.

        Raises:
            ExecutionSecretTokenRotationError: If secret_id or
                principal is None or blank, the access policy service
                does not currently authorize principal to ROTATE
                secret_id, or the token service could not issue a new
                token
        """

        self._validate_id(secret_id, "secret ID")
        self._validate_id(principal, "principal")

        self._ensure_authorized(secret_id, principal)

        with self._lock:
            try:
                new_token = self._execution_secret_token_service.issue(secret_id, principal)
            except Exception as error:
                raise ExecutionSecretTokenRotationError(
                    f"Cannot rotate token for principal {principal!r} on secret ID {secret_id!r}: issuing a "
                    f"new token failed."
                ) from error

            key = (secret_id, principal)

            rotation = ExecutionSecretTokenRotation(
                rotation_id=str(uuid4()),
                secret_id=secret_id,
                previous_token_id=self._current_token_id_by_key.get(key),
                current_token_id=new_token.token_id,
                rotated_at=datetime.now(timezone.utc),
            )

            self._rotations_by_id[rotation.rotation_id] = rotation
            self._rotation_ids_by_secret.setdefault(secret_id, []).append(rotation.rotation_id)
            self._current_token_id_by_key[key] = new_token.token_id

            return rotation

    def current(self, secret_id: str, principal: str) -> str:
        """
        Look up a principal's currently active token ID for a secret.

        Raises:
            ExecutionSecretTokenRotationError: If secret_id or
                principal is None or blank, or the principal has never
                rotated a token for the secret
        """

        self._validate_id(secret_id, "secret ID")
        self._validate_id(principal, "principal")

        with self._lock:
            token_id = self._current_token_id_by_key.get((secret_id, principal))

            if token_id is None:
                raise ExecutionSecretTokenRotationError(
                    f"Principal {principal!r} has never rotated a token for secret ID {secret_id!r}."
                )

            return token_id

    def history(self, secret_id: str) -> list:
        """
        List every rotation recorded for a secret, across every
        principal, in the order they occurred.

        Raises:
            ExecutionSecretTokenRotationError: If secret_id is None or
                blank
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            return [
                self._rotations_by_id[rotation_id]
                for rotation_id in self._rotation_ids_by_secret.get(secret_id, [])
            ]

    def revoke_previous(self, rotation_id: str) -> str:
        """
        Revoke the token a specific rotation replaced.

        Raises:
            ExecutionSecretTokenRotationError: If rotation_id is None
                or blank, no rotation is recorded under it, it has no
                previous_token_id to revoke, or the token service
                could not revoke it
        """

        self._validate_id(rotation_id, "rotation ID")

        with self._lock:
            rotation = self._resolve(rotation_id)

            if rotation.previous_token_id is None:
                raise ExecutionSecretTokenRotationError(
                    f"Rotation ID {rotation_id!r} has no previous token to revoke."
                )

            try:
                self._execution_secret_token_service.revoke(rotation.previous_token_id)
            except Exception as error:
                raise ExecutionSecretTokenRotationError(
                    f"Cannot revoke the previous token for rotation ID {rotation_id!r}."
                ) from error

            return rotation.previous_token_id

    def _ensure_authorized(self, secret_id: str, principal: str) -> None:
        try:
            authorized = self._execution_secret_access_service.authorize(
                secret_id, principal, ExecutionSecretOperation.ROTATE
            )
        except Exception as error:
            raise ExecutionSecretTokenRotationError(
                f"Cannot rotate token for principal {principal!r} on secret ID {secret_id!r}: access policy "
                f"check failed."
            ) from error

        if not authorized:
            raise ExecutionSecretTokenRotationError(
                f"Principal {principal!r} is not authorized to ROTATE secret ID {secret_id!r}."
            )

    def _resolve(self, rotation_id: str) -> ExecutionSecretTokenRotation:
        rotation = self._rotations_by_id.get(rotation_id)

        if rotation is None:
            raise ExecutionSecretTokenRotationError(f"No rotation is recorded under rotation ID {rotation_id!r}.")

        return rotation

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretTokenRotationError(f"Cannot use an empty or blank {field_name}.")
