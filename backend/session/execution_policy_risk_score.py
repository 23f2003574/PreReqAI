from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from types import (
    MappingProxyType,
)

from typing import (
    Mapping,
)

from .execution_policy_risk_error import (
    ExecutionPolicyRiskError,
)

LEVEL_LOW = "LOW"

LEVEL_MEDIUM = "MEDIUM"

LEVEL_HIGH = "HIGH"

LEVEL_CRITICAL = "CRITICAL"

LEVELS = (
    LEVEL_LOW,
    LEVEL_MEDIUM,
    LEVEL_HIGH,
    LEVEL_CRITICAL,
)

MAX_SCORE = 100


def level_for_score(score: int) -> str:
    """
    The single source of truth for mapping a score to a level, so a
    risk service and this model can never disagree on thresholds.
    """

    if score >= 75:
        return LEVEL_CRITICAL

    if score >= 50:
        return LEVEL_HIGH

    if score >= 25:
        return LEVEL_MEDIUM

    return LEVEL_LOW


@dataclass(frozen=True)
class ExecutionPolicyRiskScore:
    """
    Immutable record of a session's execution policy risk at a point
    in time.

    The score is a value object only. It performs no calculation of
    its own; reading violations, unresolved conflicts, expired
    exceptions, and enforcement history, and weighing them into this
    record is the responsibility of an execution policy risk
    service.

    Attributes:
        session_id: The identifier of the execution session this
            score was calculated for
        score: The overall risk score, from 0 to MAX_SCORE
        level: The level score falls into, per level_for_score();
            LEVEL_LOW, LEVEL_MEDIUM, LEVEL_HIGH, or LEVEL_CRITICAL
        factors: How much each contributing factor added to score,
            by factor name
        calculated_at: When this score was calculated
    """

    session_id: str

    score: int

    level: str

    factors: Mapping

    calculated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.session_id, "session ID")

        if not isinstance(self.score, int) or isinstance(self.score, bool):
            raise ExecutionPolicyRiskError(
                "Cannot build an execution policy risk score with a non-int score."
            )

        if self.score < 0 or self.score > MAX_SCORE:
            raise ExecutionPolicyRiskError(
                f"Cannot build an execution policy risk score with a score outside 0-{MAX_SCORE}."
            )

        if self.level not in LEVELS:
            raise ExecutionPolicyRiskError(
                f"Cannot build an execution policy risk score with an unknown level: {self.level!r}."
            )

        if self.level != level_for_score(self.score):
            raise ExecutionPolicyRiskError(
                f"Cannot build an execution policy risk score of {self.score} with mismatched level {self.level!r}."
            )

        if self.factors is None:
            raise ExecutionPolicyRiskError(
                "Cannot build an execution policy risk score with a None factors."
            )

        for key, value in self.factors.items():
            if not isinstance(key, str) or not key.strip():
                raise ExecutionPolicyRiskError(
                    "Cannot build an execution policy risk score with a blank factor name."
                )

            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ExecutionPolicyRiskError(
                    f"Cannot build an execution policy risk score with a negative or non-int factor {key!r}."
                )

        object.__setattr__(self, "factors", MappingProxyType(dict(self.factors)))

        if not isinstance(self.calculated_at, datetime):
            raise ExecutionPolicyRiskError(
                "Cannot build an execution policy risk score with a non-datetime calculated_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyRiskError(
                f"Cannot build an execution policy risk score with an empty or blank {field_name}."
            )
