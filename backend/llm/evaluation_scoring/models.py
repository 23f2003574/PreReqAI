from dataclasses import dataclass
from datetime import datetime

# The same normalized 0.0-1.0 range backend.llm.context_retrieval.score_context
# already uses for relevance -- one score scale for the whole repository,
# rather than a second convention invented for evaluation.
MIN_SCORE = 0.0
MAX_SCORE = 1.0


class InvalidEvaluationScoreError(ValueError):
    """Raised when an LLMEvaluationScore fails validation."""


@dataclass(frozen=True)
class LLMEvaluationScore:
    """One criterion's deterministic judgment of a Commit #2 run's output.

    score is always within [MIN_SCORE, MAX_SCORE]. rationale is never
    empty: a score with nothing explaining it would not preserve the
    criterion-level rationale this commit is required to keep.
    """

    score_id: str
    run_id: str
    criterion_id: str
    score: float
    rationale: str
    evaluated_at: datetime

    def validate(self):
        if not self.score_id or not isinstance(self.score_id, str):
            raise InvalidEvaluationScoreError("score_id is required")

        if not self.run_id or not isinstance(self.run_id, str):
            raise InvalidEvaluationScoreError("run_id is required")

        if not self.criterion_id or not isinstance(self.criterion_id, str):
            raise InvalidEvaluationScoreError("criterion_id is required")

        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise InvalidEvaluationScoreError("score must be a number")
        if not (MIN_SCORE <= self.score <= MAX_SCORE):
            raise InvalidEvaluationScoreError(
                f"score must be between {MIN_SCORE} and {MAX_SCORE}"
            )

        if not self.rationale or not isinstance(self.rationale, str):
            raise InvalidEvaluationScoreError("rationale is required")

        if not isinstance(self.evaluated_at, datetime):
            raise InvalidEvaluationScoreError("evaluated_at must be a datetime")
