from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from .execution_policy_risk_override_error import (
    ExecutionPolicyRiskOverrideError,
)

from .execution_policy_risk_score import (
    LEVELS,
)

MAXIMUM_OVERRIDABLE_LEVEL = "HIGH"


@dataclass(frozen=True)
class ExecutionPolicyRiskOverride:
    """
    Immutable record of an explicitly approved, time-bound tolerance
    for a session's risk level, up to maximum_level.

    The override is a value object only. It never modifies the
    underlying risk score it applies against; creating, validating,
    listing active, and revoking overrides is the responsibility of
    an execution policy risk override service.

    Attributes:
        override_id: The override's unique identifier
        session_id: The identifier of the execution session this
            override applies to
        maximum_level: The highest risk level, from
            execution_policy_risk_score.LEVELS, this override
            tolerates. Can never exceed MAXIMUM_OVERRIDABLE_LEVEL:
            the most severe level, CRITICAL, can never be overridden
        reason: Why this override was approved. Required and
            retained for as long as the override's record exists,
            including after it expires or is revoked
        expires_at: When this override stops applying. Required: an
            override with no expiry can never be created
        enabled: Whether this override is currently in force; a
            revoked override is inactive immediately, even before
            expires_at
    """

    override_id: str

    session_id: str

    maximum_level: str

    reason: str

    expires_at: datetime

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.override_id, "override ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.reason, "reason")

        if self.maximum_level not in LEVELS:
            raise ExecutionPolicyRiskOverrideError(
                f"Cannot build an execution policy risk override with an unknown maximum_level: {self.maximum_level!r}."
            )

        if LEVELS.index(self.maximum_level) > LEVELS.index(MAXIMUM_OVERRIDABLE_LEVEL):
            raise ExecutionPolicyRiskOverrideError(
                f"Cannot build an execution policy risk override with maximum_level {self.maximum_level!r}: "
                f"it exceeds the configured maximum of {MAXIMUM_OVERRIDABLE_LEVEL!r}."
            )

        if not isinstance(self.expires_at, datetime):
            raise ExecutionPolicyRiskOverrideError(
                "Cannot build an execution policy risk override with no expires_at."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionPolicyRiskOverrideError(
                "Cannot build an execution policy risk override with a non-bool enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyRiskOverrideError(
                f"Cannot build an execution policy risk override with an empty or blank {field_name}."
            )
