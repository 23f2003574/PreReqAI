from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from .execution_compliance_exception_error import (
    ExecutionComplianceExceptionError,
)


@dataclass(frozen=True)
class ExecutionComplianceException:
    """
    Immutable record of an explicitly approved, time-bound exception
    to a single blocking compliance rule for a single change request,
    without ever modifying the underlying rule.

    The exception is a value object only. It never disables or
    rewrites the rule it excepts; creating, validating, listing
    active, and revoking exceptions is the responsibility of an
    execution compliance exception service.

    Attributes:
        exception_id: The exception's unique identifier
        rule_id: The identifier of the blocking compliance rule this
            exception applies against
        change_id: The identifier of the change request this
            exception applies to
        reason: Why this exception was approved. Required and
            retained for as long as the exception's record exists,
            including after it expires or is revoked
        expires_at: When this exception stops applying. Required: an
            exception with no expiry can never be created
        approved_by: The identifier of who approved this exception.
            Required: an exception can never be created without an
            approver
        enabled: Whether this exception is currently in force; a
            revoked exception is inactive immediately, even before
            expires_at
    """

    exception_id: str

    rule_id: str

    change_id: str

    reason: str

    expires_at: datetime

    approved_by: str

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.exception_id, "exception ID")
        self._require_text(self.rule_id, "rule ID")
        self._require_text(self.change_id, "change ID")
        self._require_text(self.reason, "reason")
        self._require_text(self.approved_by, "approved_by")

        if not isinstance(self.expires_at, datetime):
            raise ExecutionComplianceExceptionError(
                "Cannot build an execution compliance exception with no expires_at."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionComplianceExceptionError(
                "Cannot build an execution compliance exception with a non-bool enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionComplianceExceptionError(
                f"Cannot build an execution compliance exception with an empty or blank {field_name}."
            )
