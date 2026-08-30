from dataclasses import dataclass
from datetime import datetime


class InvalidEvaluationMatrixError(ValueError):
    """Raised when an LLMEvaluationMatrix fails validation."""


@dataclass(frozen=True)
class LLMEvaluationMatrix:
    """A snapshot aggregating Commit #4 scores across providers/models for one task_type.

    runs is exactly the run_id list build() was given; criteria is the
    Commit #3 enabled criterion_ids for task_type at build time.
    aggregate_scores holds {"by_provider": ..., "by_model": ...}, each a
    dict keyed by provider (or (provider, model)) whose value never
    fabricates a score for a group with no successful run -- "overall" is
    None and run_count is 0 for a provider/model that only produced
    excluded (non-SUCCEEDED) runs, with those runs listed explicitly under
    excluded_run_ids rather than silently counted as zero.
    """

    matrix_id: str
    task_type: str
    runs: list
    criteria: list
    aggregate_scores: dict
    generated_at: datetime

    def validate(self):
        if not self.matrix_id or not isinstance(self.matrix_id, str):
            raise InvalidEvaluationMatrixError("matrix_id is required")

        if not self.task_type or not isinstance(self.task_type, str):
            raise InvalidEvaluationMatrixError("task_type is required")

        if not isinstance(self.runs, list):
            raise InvalidEvaluationMatrixError("runs must be a list")

        if not isinstance(self.criteria, list):
            raise InvalidEvaluationMatrixError("criteria must be a list")

        if not isinstance(self.aggregate_scores, dict):
            raise InvalidEvaluationMatrixError("aggregate_scores must be a dict")
        if not {"by_provider", "by_model"} <= set(self.aggregate_scores):
            raise InvalidEvaluationMatrixError(
                "aggregate_scores must contain 'by_provider' and 'by_model'"
            )

        if not isinstance(self.generated_at, datetime):
            raise InvalidEvaluationMatrixError("generated_at must be a datetime")
