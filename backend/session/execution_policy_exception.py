from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from .execution_policy_exception_error import (
    ExecutionPolicyExceptionError,
)


@dataclass(frozen=True)
class ExecutionPolicyException:
    """
    Immutable record of an explicitly approved, time-bound exception
    to a single rule of a policy.

    The exception is a value object only. It never modifies the base
    policy it applies against; creating, validating, listing active,
    and revoking exceptions is the responsibility of an execution
    policy exception service.

    Attributes:
        exception_id: The exception's unique identifier
        policy_id: The identifier of the policy this exception
            applies against
        scope_id: The identifier of the scope this exception is
            approved for
        rule: The specific rule this exception excepts
        expires_at: When this exception stops applying. Required: an
            exception with no expiry can never be created
        reason: Why this exception was approved. Required and
            retained for as long as the exception's record exists,
            including after it expires or is revoked
    """

    exception_id: str

    policy_id: str

    scope_id: str

    rule: str

    expires_at: datetime

    reason: str

    def __post_init__(self):
        self._require_text(self.exception_id, "exception ID")
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.scope_id, "scope ID")
        self._require_text(self.rule, "rule")
        self._require_text(self.reason, "reason")

        if not isinstance(self.expires_at, datetime):
            raise ExecutionPolicyExceptionError(
                "Cannot build an execution policy exception with no expires_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyExceptionError(
                f"Cannot build an execution policy exception with an empty or blank {field_name}."
            )
