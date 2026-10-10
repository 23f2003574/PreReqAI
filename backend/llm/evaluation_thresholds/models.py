from dataclasses import dataclass

from ..evaluation_scoring import MAX_SCORE, MIN_SCORE


class InvalidEvaluationThresholdError(ValueError):
    """Raised when an LLMEvaluationThreshold fails validation."""


@dataclass
class LLMEvaluationThreshold:
    """The minimum Commit #4 score a criterion's output must clear.

    minimum_score is checked on the exact [MIN_SCORE, MAX_SCORE] scale
    Commit #4's LLMEvaluationScore already uses -- a threshold and the
    score it is compared against always mean the same range, never a
    second one invented for thresholds.
    """

    threshold_id: str
    criterion_id: str
    minimum_score: float
    enabled: bool = True

    def validate(self):
        if not self.threshold_id or not isinstance(self.threshold_id, str):
            raise InvalidEvaluationThresholdError("threshold_id is required")

        if not self.criterion_id or not isinstance(self.criterion_id, str):
            raise InvalidEvaluationThresholdError("criterion_id is required")

        if isinstance(self.minimum_score, bool) or not isinstance(
            self.minimum_score, (int, float)
        ):
            raise InvalidEvaluationThresholdError("minimum_score must be a number")
        if not (MIN_SCORE <= self.minimum_score <= MAX_SCORE):
            raise InvalidEvaluationThresholdError(
                f"minimum_score must be between {MIN_SCORE} and {MAX_SCORE}"
            )

        if not isinstance(self.enabled, bool):
            raise InvalidEvaluationThresholdError("enabled must be a bool")
