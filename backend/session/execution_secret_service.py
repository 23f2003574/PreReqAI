from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .execution_secret import (
    ExecutionSecret,
)

from .execution_secret_error import (
    ExecutionSecretError,
)


class ExecutionSecretService:
    """
    Registers execution-scoped secrets, keyed by a unique secret ID
    and grouped by the session they are scoped to.

    The service's responsibility is registry bookkeeping only. It
    never stores or returns a raw secret value: an ExecutionSecret
    only ever carries a value_ref, so lookups can be handed back
    freely without exposing what they protect.

    Behavior:
    - A session may have any number of registered secrets
    - A secret's name must be unique within its session; registering
      a second secret under a name already in use for that session is
      rejected, even if the existing one has expired
    - get() returns None, not an error, for a miss: no secret was
      ever registered under that name for that session, or the
      secret it finds has expired
    - remove() immediately revokes access to a secret; a subsequent
      get() for its name is a miss
    - Secrets are isolated per session: a secret registered for one
      session is never visible to another

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._secrets = {}
        self._secret_id_by_key = {}
        self._secret_ids_by_session = {}
        self._secret_ids_in_order = []
        self._lock = RLock()

    def register(self, session_id: str, secret: ExecutionSecret) -> ExecutionSecret:
        """
        Register a secret on behalf of a session.

        Raises:
            ExecutionSecretError: If session_id is None or blank,
                secret is not an ExecutionSecret belonging to
                session_id, the secret ID is already registered, or
                its name is already in use for that session
        """

        self._validate_id(session_id, "session ID")

        if not isinstance(secret, ExecutionSecret):
            raise ExecutionSecretError(
                "Cannot register an invalid secret: secret must be an ExecutionSecret."
            )

        if secret.session_id != session_id:
            raise ExecutionSecretError(
                f"Cannot register a secret for session ID {secret.session_id!r} on behalf of "
                f"session ID {session_id!r}."
            )

        with self._lock:
            if secret.secret_id in self._secrets:
                raise ExecutionSecretError(
                    f"Secret ID {secret.secret_id!r} is already registered."
                )

            key = (session_id, secret.name)

            if key in self._secret_id_by_key:
                raise ExecutionSecretError(
                    f"Name {secret.name!r} is already registered for session ID {session_id!r}."
                )

            self._secrets[secret.secret_id] = secret
            self._secret_id_by_key[key] = secret.secret_id
            self._secret_ids_by_session.setdefault(session_id, []).append(secret.secret_id)
            self._secret_ids_in_order.append(secret.secret_id)

            return secret

    def get(self, session_id: str, name: str) -> ExecutionSecret | None:
        """
        Look up a session's secret by name. Returns None for a miss:
        nothing was ever registered under that name for that session,
        or the secret it finds has expired.

        Raises:
            ExecutionSecretError: If session_id or name is None or
                blank
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(name, "name")

        with self._lock:
            secret_id = self._secret_id_by_key.get((session_id, name))

            if secret_id is None:
                return None

            secret = self._secrets[secret_id]

            if self._is_expired(secret):
                return None

            return secret

    def remove(self, secret_id: str) -> ExecutionSecret:
        """
        Remove a registered secret, immediately revoking access to
        it.

        Raises:
            ExecutionSecretError: If secret_id is None or blank, or
                no secret is registered under it
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            return self._remove(secret_id)

    def expired(self) -> list:
        """
        List every currently expired secret that has not yet been
        cleaned up, across all sessions, in the order they were
        registered.
        """

        with self._lock:
            return [
                self._secrets[secret_id]
                for secret_id in self._secret_ids_in_order
                if self._is_expired(self._secrets[secret_id])
            ]

    def cleanup(self) -> list:
        """
        Remove every currently expired secret.

        Returns the secrets that were removed, in the order they were
        registered.
        """

        with self._lock:
            expired_ids = [
                secret_id
                for secret_id in self._secret_ids_in_order
                if self._is_expired(self._secrets[secret_id])
            ]

            return [self._remove(secret_id) for secret_id in expired_ids]

    def _remove(self, secret_id: str) -> ExecutionSecret:
        secret = self._resolve(secret_id)

        del self._secrets[secret_id]

        key = (secret.session_id, secret.name)

        if self._secret_id_by_key.get(key) == secret_id:
            del self._secret_id_by_key[key]

        self._secret_ids_by_session[secret.session_id].remove(secret_id)
        self._secret_ids_in_order.remove(secret_id)

        return secret

    def _resolve(self, secret_id: str) -> ExecutionSecret:
        secret = self._secrets.get(secret_id)

        if secret is None:
            raise ExecutionSecretError(f"No secret is known under secret ID {secret_id!r}.")

        return secret

    def _is_expired(self, secret: ExecutionSecret) -> bool:
        return secret.expires_at is not None and secret.expires_at <= datetime.now(timezone.utc)

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretError(f"Cannot use an empty or blank {field_name}.")
