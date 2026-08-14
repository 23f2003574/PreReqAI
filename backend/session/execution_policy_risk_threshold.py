from dataclasses import (
    dataclass,
)

from .execution_policy_risk_score import (
    LEVELS,
    MAX_SCORE,
)

from .execution_policy_risk_threshold_error import (
    ExecutionPolicyRiskThresholdError,
)

ACTION_ALLOW = "ALLOW"

ACTION_WARN = "WARN"

ACTION_BLOCK = "BLOCK"

ACTIONS = (
    ACTION_ALLOW,
    ACTION_WARN,
    ACTION_BLOCK,
)


@dataclass(frozen=True)
class ExecutionPolicyRiskThreshold:
    """
    Immutable, configurable rule mapping a minimum risk score to an
    enforcement action.

    The threshold is a value object only. It performs no evaluation
    of its own; registering thresholds and deciding which one
    applies to a session's current risk score is the responsibility
    of an execution policy risk threshold service.

    Attributes:
        threshold_id: The threshold's unique identifier
        level: The risk level, from execution_policy_risk_score.LEVELS,
            this threshold is configured for
        minimum_score: The lowest score, inclusive, at which this
            threshold applies
        action: The action to take when this threshold applies, one
            of ACTIONS
        enabled: Whether this threshold currently applies; a
            disabled threshold is never matched
    """

    threshold_id: str

    level: str

    minimum_score: int

    action: str

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.threshold_id, "threshold ID")

        if self.level not in LEVELS:
            raise ExecutionPolicyRiskThresholdError(
                f"Cannot build an execution policy risk threshold with an unknown level: {self.level!r}."
            )

        if not isinstance(self.minimum_score, int) or isinstance(self.minimum_score, bool):
            raise ExecutionPolicyRiskThresholdError(
                "Cannot build an execution policy risk threshold with a non-int minimum_score."
            )

        if self.minimum_score < 0 or self.minimum_score > MAX_SCORE:
            raise ExecutionPolicyRiskThresholdError(
                f"Cannot build an execution policy risk threshold with a minimum_score outside 0-{MAX_SCORE}."
            )

        if self.action not in ACTIONS:
            raise ExecutionPolicyRiskThresholdError(
                f"Cannot build an execution policy risk threshold with an unknown action: {self.action!r}."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionPolicyRiskThresholdError(
                "Cannot build an execution policy risk threshold with a non-bool enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyRiskThresholdError(
                f"Cannot build an execution policy risk threshold with an empty or blank {field_name}."
            )
