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

from .execution_secret_access_token import (
    ExecutionSecretAccessToken,
)

from .execution_secret_operation import (
    ExecutionSecretOperation,
)

from .execution_secret_token_error import (
    ExecutionSecretTokenError,
)

_DEFAULT_TTL = timedelta(minutes=5)


class ExecutionSecretTokenService:
    """
    Issues short-lived tokens for authorized secret access, so a
    caller can be handed a token instead of a persistent permission:
    using an existing execution secret trust service and access
    policy service to confirm a principal is currently authorized to
    READ a secret before a token is issued.

    The service's responsibility is token bookkeeping only. It does
    not resolve or store raw secret values, and a token never carries
    one; presenting a token proves prior authorization, nothing more.

    Behavior:
    - issue() requires both the trust service and the access policy
      service to currently authorize the principal to READ the
      secret
    - A token past its expires_at immediately fails validate(), even
      before that is reflected in its stored status
    - revoke() ends an ACTIVE token's access immediately; a token
      already revoked or expired cannot be revoked again
    - active() and expired() are unaffected by tokens that were never
      effectively active in the first place

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_secret_trust_service, execution_secret_access_service, ttl: timedelta = _DEFAULT_TTL):
        """
        Args:
            execution_secret_trust_service: The service used to
                confirm a principal's trust level currently authorizes
                READ on a secret. Any object exposing
                `authorize(principal, operation)` is accepted
            execution_secret_access_service: The service used to
                confirm a principal currently holds a per-secret grant
                to READ the secret. Any object exposing
                `authorize(secret_id, principal, operation)` is
                accepted
            ttl: How long a newly issued token stays active before it
                expires
        """

        if not isinstance(ttl, timedelta):
            raise ExecutionSecretTokenError("Cannot use a non-timedelta ttl.")

        self._execution_secret_trust_service = execution_secret_trust_service
        self._execution_secret_access_service = execution_secret_access_service
        self._ttl = ttl
        self._tokens_by_id = {}
        self._token_ids_in_order = []
        self._token_ids_by_principal = {}
        self._lock = RLock()

    def issue(self, secret_id: str, principal: str) -> ExecutionSecretAccessToken:
        """
        Issue a short-lived token granting a principal access to a
        secret.

        Raises:
            ExecutionSecretTokenError: If secret_id or principal is
                None or blank, or either the trust service or the
                access policy service does not currently authorize
                principal to READ secret_id
        """

        self._validate_id(secret_id, "secret ID")
        self._validate_id(principal, "principal")

        self._ensure_authorized(secret_id, principal)

        with self._lock:
            token_id = str(uuid4())

            token = ExecutionSecretAccessToken(
                token_id=token_id,
                secret_id=secret_id,
                principal=principal,
                expires_at=datetime.now(timezone.utc) + self._ttl,
            )

            self._tokens_by_id[token_id] = token
            self._token_ids_in_order.append(token_id)
            self._token_ids_by_principal.setdefault(principal, []).append(token_id)

            return token

    def validate(self, token_id: str) -> bool:
        """
        Check whether a token is currently valid: known, ACTIVE, and
        not past its expiry.

        Raises:
            ExecutionSecretTokenError: If token_id is None or blank
        """

        self._validate_id(token_id, "token ID")

        with self._lock:
            token = self._tokens_by_id.get(token_id)

            if token is None:
                return False

            return self._effective_status(token) == "ACTIVE"

    def revoke(self, token_id: str) -> ExecutionSecretAccessToken:
        """
        Revoke a token, ending its access immediately.

        Raises:
            ExecutionSecretTokenError: If token_id is None or blank,
                no token is known under it, or it is not effectively
                ACTIVE
        """

        self._validate_id(token_id, "token ID")

        with self._lock:
            token = self._resolve(token_id)

            if self._effective_status(token) != "ACTIVE":
                raise ExecutionSecretTokenError(f"Cannot revoke token ID {token_id!r}: it is not ACTIVE.")

            updated = replace(token, status="REVOKED")
            self._tokens_by_id[token_id] = updated

            return updated

    def active(self, principal: str) -> list:
        """
        List a principal's effectively active tokens, in the order
        they were issued.

        Raises:
            ExecutionSecretTokenError: If principal is None or blank
        """

        self._validate_id(principal, "principal")

        with self._lock:
            return [
                self._tokens_by_id[token_id]
                for token_id in self._token_ids_by_principal.get(principal, [])
                if self._effective_status(self._tokens_by_id[token_id]) == "ACTIVE"
            ]

    def expired(self) -> list:
        """
        List every ACTIVE token that is currently past its expiry,
        across every principal, in the order they were issued.
        """

        with self._lock:
            return [
                self._tokens_by_id[token_id]
                for token_id in self._token_ids_in_order
                if self._tokens_by_id[token_id].status == "ACTIVE" and self._is_expired(self._tokens_by_id[token_id])
            ]

    def _ensure_authorized(self, secret_id: str, principal: str) -> None:
        try:
            trust_authorized = self._execution_secret_trust_service.authorize(principal, ExecutionSecretOperation.READ)
            access_authorized = self._execution_secret_access_service.authorize(
                secret_id, principal, ExecutionSecretOperation.READ
            )
        except Exception as error:
            raise ExecutionSecretTokenError(
                f"Cannot issue a token for principal {principal!r} on secret ID {secret_id!r}: policy check "
                f"failed."
            ) from error

        if not (trust_authorized and access_authorized):
            raise ExecutionSecretTokenError(
                f"Principal {principal!r} is not authorized to READ secret ID {secret_id!r}."
            )

    def _effective_status(self, token: ExecutionSecretAccessToken) -> str:
        if token.status == "ACTIVE" and self._is_expired(token):
            return "EXPIRED"

        return token.status

    def _is_expired(self, token: ExecutionSecretAccessToken) -> bool:
        return token.expires_at <= datetime.now(timezone.utc)

    def _resolve(self, token_id: str) -> ExecutionSecretAccessToken:
        token = self._tokens_by_id.get(token_id)

        if token is None:
            raise ExecutionSecretTokenError(f"No token is known under token ID {token_id!r}.")

        return token

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionSecretTokenError(f"Cannot use an empty or blank {field_name}.")
