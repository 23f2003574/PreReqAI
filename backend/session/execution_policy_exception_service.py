from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_policy_exception import (
    ExecutionPolicyException,
)

from .execution_policy_exception_error import (
    ExecutionPolicyExceptionError,
)


class ExecutionPolicyExceptionService:
    """
    Grants explicitly approved, time-bound exceptions to individual
    policy rules, using an existing execution policy registry as the
    source of truth for whether the exempted policy exists. Policy
    evaluation, built by an earlier commit, is assumed to already
    exist and is unaffected by this service: an exception is a
    record a caller may consult before treating a rule violation as
    blocking, never a change to the policy's own rules.

    The base policy a caller registered is never weakened: an
    exception here is scoped to a single (policy_id, scope_id, rule)
    grant and never mutates the ExecutionPolicy it applies against.

    Behavior:
    - create() requires the exempted policy to already be
      registered, and requires a non-None expires_at; an exception
      can never be created without either
    - An exception is active only while it is neither revoked nor
      past its expires_at; revoking or letting it expire never
      deletes its record or its reason
    - active() lists only the exceptions currently active for a
      scope
    - expired() lists every recorded exception whose expires_at has
      passed, regardless of scope or revocation

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_policy_service):
        """
        Args:
            execution_policy_service: The registry used to confirm a
                policy exists before an exception to one of its
                rules can be created. Any object exposing
                `get(policy_id)` is accepted
        """

        self._execution_policy_service = execution_policy_service
        self._exceptions_by_id = {}
        self._exception_ids_by_scope = {}
        self._revoked_ids = set()
        self._lock = RLock()

    def create(
        self,
        policy_id: str,
        scope_id: str,
        rule: str,
        reason: str,
        expires_at: datetime,
    ) -> ExecutionPolicyException:
        """
        Create a new exception.

        Raises:
            ExecutionPolicyExceptionError: If expires_at is None, or
                any other field is invalid
            ExecutionPolicyError: If no policy is registered under
                policy_id
        """

        self._execution_policy_service.get(policy_id)

        if expires_at is None:
            raise ExecutionPolicyExceptionError(
                "Cannot create an execution policy exception with no expires_at."
            )

        with self._lock:
            exception = ExecutionPolicyException(
                exception_id=str(uuid4()),
                policy_id=policy_id,
                scope_id=scope_id,
                rule=rule,
                expires_at=expires_at,
                reason=reason,
            )

            self._exceptions_by_id[exception.exception_id] = exception
            self._exception_ids_by_scope.setdefault(scope_id, []).append(exception.exception_id)

            return exception

    def validate(self, exception_id: str) -> bool:
        """
        Check whether an exception is currently active.

        Raises:
            ExecutionPolicyExceptionError: If exception_id is None or
                blank, or no exception is recorded under it
        """

        self._validate_text(exception_id, "exception ID")

        with self._lock:
            return self._is_active(self._resolve(exception_id))

    def active(self, scope_id: str) -> list:
        """
        List the currently active exceptions for a scope.

        Raises:
            ExecutionPolicyExceptionError: If scope_id is None or
                blank
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            return [
                self._exceptions_by_id[exception_id]
                for exception_id in self._exception_ids_by_scope.get(scope_id, [])
                if self._is_active(self._exceptions_by_id[exception_id])
            ]

    def revoke(self, exception_id: str) -> ExecutionPolicyException:
        """
        Revoke an exception, so it is inactive immediately, even if
        it has not yet expired.

        Raises:
            ExecutionPolicyExceptionError: If exception_id is None or
                blank, or no exception is recorded under it
        """

        self._validate_text(exception_id, "exception ID")

        with self._lock:
            exception = self._resolve(exception_id)

            self._revoked_ids.add(exception_id)

            return exception

    def expired(self) -> list:
        """
        List every recorded exception whose expires_at has passed,
        regardless of scope or revocation.
        """

        with self._lock:
            now = datetime.now(timezone.utc)

            return [exception for exception in self._exceptions_by_id.values() if exception.expires_at <= now]

    def _is_active(self, exception: ExecutionPolicyException) -> bool:
        if exception.exception_id in self._revoked_ids:
            return False

        return exception.expires_at > datetime.now(timezone.utc)

    def _resolve(self, exception_id: str) -> ExecutionPolicyException:
        exception = self._exceptions_by_id.get(exception_id)

        if exception is None:
            raise ExecutionPolicyExceptionError(f"No exception is recorded under exception ID {exception_id!r}.")

        return exception

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyExceptionError(f"Cannot use an empty or blank {field_name}.")
