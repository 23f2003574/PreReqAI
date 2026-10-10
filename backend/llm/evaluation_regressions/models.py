from dataclasses import dataclass

REGRESSED = "REGRESSED"
IMPROVED = "IMPROVED"
UNCHANGED = "UNCHANGED"
UNKNOWN = "UNKNOWN"
STATUSES = frozenset({REGRESSED, IMPROVED, UNCHANGED, UNKNOWN})

SEVERITY_NONE = "NONE"
SEVERITY_MINOR = "MINOR"
SEVERITY_CRITICAL = "CRITICAL"
SEVERITIES = frozenset({SEVERITY_NONE, SEVERITY_MINOR, SEVERITY_CRITICAL})


class InvalidEvaluationRegressionError(ValueError):
    """Raised when an LLMEvaluationRegression fails validation."""


@dataclass(frozen=True)
class LLMEvaluationRegression:
    """One criterion's classified change between a Commit #6 baseline/candidate pair.

    delta is exactly Commit #6's criterion_delta -- None when the criterion
    could not be scored on one or both sides, in which case status is
    UNKNOWN and severity is SEVERITY_NONE rather than a fabricated
    judgment. severity is only ever above SEVERITY_NONE when status is
    REGRESSED.
    """

    regression_id: str
    baseline_run: str
    candidate_run: str
    criterion: str
    delta: float
    severity: str
    status: str

    def validate(self):
        if not self.regression_id or not isinstance(self.regression_id, str):
            raise InvalidEvaluationRegressionError("regression_id is required")

        if not self.baseline_run or not isinstance(self.baseline_run, str):
            raise InvalidEvaluationRegressionError("baseline_run is required")

        if not self.candidate_run or not isinstance(self.candidate_run, str):
            raise InvalidEvaluationRegressionError("candidate_run is required")

        if not self.criterion or not isinstance(self.criterion, str):
            raise InvalidEvaluationRegressionError("criterion is required")

        if self.delta is not None and (
            isinstance(self.delta, bool) or not isinstance(self.delta, (int, float))
        ):
            raise InvalidEvaluationRegressionError("delta must be a number or None")

        if self.severity not in SEVERITIES:
            raise InvalidEvaluationRegressionError(f"severity must be one of {sorted(SEVERITIES)}")

        if self.status not in STATUSES:
            raise InvalidEvaluationRegressionError(f"status must be one of {sorted(STATUSES)}")

        if self.status != REGRESSED and self.severity != SEVERITY_NONE:
            raise InvalidEvaluationRegressionError(
                "severity above NONE is only meaningful when status is REGRESSED"
            )
