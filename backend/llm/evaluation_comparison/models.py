from dataclasses import dataclass
from datetime import datetime

BASELINE = "baseline"
CANDIDATE = "candidate"
TIE = "tie"
WINNERS = frozenset({BASELINE, CANDIDATE, TIE})


class InvalidEvaluationComparisonError(ValueError):
    """Raised when an LLMEvaluationComparison fails validation."""


@dataclass(frozen=True)
class LLMEvaluationComparison:
    """A read-only comparison of two completed runs' Commit #4 scores.

    criterion_deltas is a dict keyed by criterion_id, each value a
    {"criterion_id", "baseline_score", "candidate_score", "delta"} entry --
    a score of None means that criterion was never scored for that run
    (e.g. disabled), preserved explicitly rather than dropped. overall_delta
    and winner are derived only from Commit #4's own overall() scores; this
    record invents no second scoring model and never mutates anything it
    compares.
    """

    comparison_id: str
    baseline_run: str
    candidate_run: str
    criterion_deltas: dict
    overall_delta: float
    winner: str
    created_at: datetime

    def validate(self):
        if not self.comparison_id or not isinstance(self.comparison_id, str):
            raise InvalidEvaluationComparisonError("comparison_id is required")

        if not self.baseline_run or not isinstance(self.baseline_run, str):
            raise InvalidEvaluationComparisonError("baseline_run is required")

        if not self.candidate_run or not isinstance(self.candidate_run, str):
            raise InvalidEvaluationComparisonError("candidate_run is required")

        if not isinstance(self.criterion_deltas, dict):
            raise InvalidEvaluationComparisonError("criterion_deltas must be a dict")

        if isinstance(self.overall_delta, bool) or not isinstance(self.overall_delta, (int, float)):
            raise InvalidEvaluationComparisonError("overall_delta must be a number")

        if self.winner not in WINNERS:
            raise InvalidEvaluationComparisonError(
                f"winner must be one of {sorted(WINNERS)}"
            )

        if not isinstance(self.created_at, datetime):
            raise InvalidEvaluationComparisonError("created_at must be a datetime")
