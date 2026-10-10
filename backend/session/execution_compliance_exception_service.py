from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_compliance_exception import (
    ExecutionComplianceException,
)

from .execution_compliance_exception_error import (
    ExecutionComplianceExceptionError,
)

from .execution_compliance_rule import (
    SEVERITY_BLOCKING,
)


class ExecutionComplianceExceptionService:
    """
    Grants explicitly approved, time-bound exceptions to a single
    blocking compliance rule for a single change request, without
    ever modifying, disabling, or rewriting the underlying rule an
    existing execution compliance service registered.

    It operates over a compliance service supplied at construction
    time to resolve whether a rule exists and is currently blocking;
    it never registers, evaluates, or disables a rule itself.

    Behavior:
    - create() only succeeds against a rule that currently exists and
      is BLOCKING; a WARNING rule or an unknown rule can never have
      an exception created against it
    - create() requires a non-blank approver and a non-blank reason;
      an exception can never be created without either
    - create() requires a non-None expires_at; an exception with no
      expiry can never be created
    - An exception is active only while it is enabled and not past
      its expires_at; revoking or letting it expire never deletes its
      record, and an expired or revoked exception can never bypass
      the violation it was created against
    - active() lists only the exceptions currently active for a
      change request

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, compliance_service):
        """
        Args:
            compliance_service: The service used to resolve whether a
                rule exists and its severity. Any object exposing
                `find(rule_id)`, returning None or an object with a
                `severity` attribute, is accepted
        """

        if compliance_service is None:
            raise ExecutionComplianceExceptionError(
                "Cannot initialize execution compliance exception service with a None compliance service."
            )

        self._compliance_service = compliance_service
        self._exceptions_by_id = {}
        self._exception_ids_by_change = {}
        self._lock = RLock()

    def create(
        self,
        rule_id: str,
        change_id: str,
        reason: str,
        approver: str,
        expires_at: datetime,
    ) -> ExecutionComplianceException:
        """
        Create a new, active exception to a blocking compliance rule.

        Raises:
            ExecutionComplianceExceptionError: If rule_id, change_id,
                reason, or approver is None or blank, expires_at is
                None, no rule is registered under rule_id, or the
                rule is not BLOCKING
        """

        self._validate_text(rule_id, "rule ID")

        with self._lock:
            rule = self._compliance_service.find(rule_id)

            if rule is None:
                raise ExecutionComplianceExceptionError(
                    f"Cannot create an exception for rule ID {rule_id!r}: no rule is registered under it."
                )

            if rule.severity != SEVERITY_BLOCKING:
                raise ExecutionComplianceExceptionError(
                    f"Cannot create an exception for rule ID {rule_id!r}: it is not a blocking rule."
                )

            exception = ExecutionComplianceException(
                exception_id=str(uuid4()),
                rule_id=rule_id,
                change_id=change_id,
                reason=reason,
                expires_at=expires_at,
                approved_by=approver,
            )

            self._exceptions_by_id[exception.exception_id] = exception
            self._exception_ids_by_change.setdefault(change_id, []).append(exception.exception_id)

            return exception

    def validate(self, exception_id: str) -> bool:
        """
        Check whether an exception is currently active.

        Raises:
            ExecutionComplianceExceptionError: If exception_id is
                None or blank, or no exception is recorded under it
        """

        self._validate_text(exception_id, "exception ID")

        with self._lock:
            return self._is_active(self._resolve(exception_id))

    def active(self, change_id: str) -> list:
        """
        List the currently active exceptions for a change request.

        Raises:
            ExecutionComplianceExceptionError: If change_id is None
                or blank
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            return [
                self._exceptions_by_id[exception_id]
                for exception_id in self._exception_ids_by_change.get(change_id, [])
                if self._is_active(self._exceptions_by_id[exception_id])
            ]

    def revoke(self, exception_id: str) -> ExecutionComplianceException:
        """
        Revoke an exception, so it is inactive immediately, even if
        it has not yet expired.

        Raises:
            ExecutionComplianceExceptionError: If exception_id is
                None or blank, or no exception is recorded under it
        """

        self._validate_text(exception_id, "exception ID")

        with self._lock:
            exception = self._resolve(exception_id)

            updated = replace(exception, enabled=False)
            self._exceptions_by_id[exception_id] = updated

            return updated

    def expired(self) -> list:
        """
        List every recorded exception whose expires_at has passed,
        regardless of change request or revocation.
        """

        with self._lock:
            now = datetime.now(timezone.utc)

            return [exception for exception in self._exceptions_by_id.values() if exception.expires_at <= now]

    def _is_active(self, exception: ExecutionComplianceException) -> bool:
        if not exception.enabled:
            return False

        return exception.expires_at > datetime.now(timezone.utc)

    def _resolve(self, exception_id: str) -> ExecutionComplianceException:
        exception = self._exceptions_by_id.get(exception_id)

        if exception is None:
            raise ExecutionComplianceExceptionError(f"No exception is recorded under exception ID {exception_id!r}.")

        return exception

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionComplianceExceptionError(f"Cannot use an empty or blank {field_name}.")
