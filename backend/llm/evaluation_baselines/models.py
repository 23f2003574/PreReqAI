from dataclasses import dataclass
from datetime import datetime

from ..evaluation_scoring import MAX_SCORE, MIN_SCORE

ACTIVE = "ACTIVE"
SUPERSEDED = "SUPERSEDED"
STATUSES = frozenset({ACTIVE, SUPERSEDED})


class InvalidEvaluationBaselineError(ValueError):
    """Raised when an LLMEvaluationBaseline fails validation."""


@dataclass
class LLMEvaluationBaseline:
    """The explicitly accepted, known-good Commit #9 dataset run for one dataset.

    run_id is a Commit #9 dataset_run_id, never a bare case-level run_id --
    a baseline is always a whole reproducible dataset benchmark, not one
    case. overall_score is on the same [MIN_SCORE, MAX_SCORE] scale Commit
    #4 already uses. status flips from ACTIVE to SUPERSEDED when replace()
    accepts a new baseline for the same dataset_id; the record itself is
    never deleted, preserving it as history.
    """

    baseline_id: str
    dataset_id: str
    run_id: str
    provider: str
    model: str
    overall_score: float
    accepted_at: datetime
    status: str

    def validate(self):
        if not self.baseline_id or not isinstance(self.baseline_id, str):
            raise InvalidEvaluationBaselineError("baseline_id is required")

        if not self.dataset_id or not isinstance(self.dataset_id, str):
            raise InvalidEvaluationBaselineError("dataset_id is required")

        if not self.run_id or not isinstance(self.run_id, str):
            raise InvalidEvaluationBaselineError("run_id is required")

        if not self.provider or not isinstance(self.provider, str):
            raise InvalidEvaluationBaselineError("provider is required")

        if not self.model or not isinstance(self.model, str):
            raise InvalidEvaluationBaselineError("model is required")

        if isinstance(self.overall_score, bool) or not isinstance(self.overall_score, (int, float)):
            raise InvalidEvaluationBaselineError("overall_score must be a number")
        if not (MIN_SCORE <= self.overall_score <= MAX_SCORE):
            raise InvalidEvaluationBaselineError(
                f"overall_score must be between {MIN_SCORE} and {MAX_SCORE}"
            )

        if not isinstance(self.accepted_at, datetime):
            raise InvalidEvaluationBaselineError("accepted_at must be a datetime")

        if self.status not in STATUSES:
            raise InvalidEvaluationBaselineError(f"status must be one of {sorted(STATUSES)}")
