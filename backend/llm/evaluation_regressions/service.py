from ..evaluation_comparison import LLMEvaluationComparisonService
from ..evaluation_thresholds import LLMEvaluationThresholdService, UnknownEvaluationThresholdError
from .models import (
    IMPROVED,
    REGRESSED,
    SEVERITY_CRITICAL,
    SEVERITY_MINOR,
    SEVERITY_NONE,
    UNCHANGED,
    UNKNOWN,
    LLMEvaluationRegression,
)

# A delta smaller in magnitude than this is treated as noise, not a
# regression -- Commit #4 scores are deterministic match ratios, so tiny
# negative deltas can arise from a single expected_property flipping on a
# case with many of them.
REGRESSION_EPSILON = 0.05

# A delta at or below this, with no configured threshold to say otherwise,
# is severe enough to flag as CRITICAL on magnitude alone.
CRITICAL_DELTA = -0.3


class LLMEvaluationRegressionService:
    """Flags per-criterion regressions between two Commit #6-compatible runs.

    Reuses Commit #6's LLMEvaluationComparisonService for the comparison
    itself (compatibility check, matching criteria, missing-criterion
    preservation, and the scores it is built on) and Commit #5's
    LLMEvaluationThresholdService for the accepted quality bar where one is
    configured -- no second scoring or comparison system, and analyze()
    never mutates either.
    """

    def __init__(
        self,
        comparison_service: LLMEvaluationComparisonService,
        threshold_service: LLMEvaluationThresholdService,
    ):
        self._comparison_service = comparison_service
        self._threshold_service = threshold_service
        self._regressions = {}
        self._by_candidate = {}
        self._counter = 0

    def _classify(self, criterion_id: str, candidate_score, delta):
        if delta is None:
            return UNKNOWN, SEVERITY_NONE

        if delta > REGRESSION_EPSILON:
            return IMPROVED, SEVERITY_NONE
        if delta >= -REGRESSION_EPSILON:
            return UNCHANGED, SEVERITY_NONE

        try:
            threshold = self._threshold_service.get(criterion_id)
        except UnknownEvaluationThresholdError:
            threshold = None

        breaches_threshold = (
            threshold is not None
            and threshold.enabled
            and candidate_score is not None
            and candidate_score < threshold.minimum_score
        )
        if breaches_threshold or delta <= CRITICAL_DELTA:
            return REGRESSED, SEVERITY_CRITICAL

        return REGRESSED, SEVERITY_MINOR

    def analyze(self, baseline_run: str, candidate_run: str) -> list:
        """Compare two runs and classify every matched criterion; read-only.

        Compatibility (same task_type) is enforced by Commit #6's compare()
        itself, whose IncompatibleEvaluationCasesError propagates unchanged.
        """
        comparison = self._comparison_service.compare(baseline_run, candidate_run)

        regressions = []
        for criterion_id in sorted(comparison.criterion_deltas):
            entry = comparison.criterion_deltas[criterion_id]
            status, severity = self._classify(criterion_id, entry["candidate_score"], entry["delta"])

            self._counter += 1
            regression = LLMEvaluationRegression(
                regression_id=f"eval-regression-{self._counter}",
                baseline_run=baseline_run,
                candidate_run=candidate_run,
                criterion=criterion_id,
                delta=entry["delta"],
                severity=severity,
                status=status,
            )
            regression.validate()
            regressions.append(regression)

        for regression in regressions:
            self._regressions[regression.regression_id] = regression
        self._by_candidate.setdefault(candidate_run, []).extend(
            regression.regression_id for regression in regressions
        )

        return regressions

    def regressions(self, candidate_run: str) -> list:
        """Every recorded, meaningful regression (status REGRESSED) for candidate_run."""
        return [
            self._regressions[regression_id]
            for regression_id in self._by_candidate.get(candidate_run, [])
            if self._regressions[regression_id].status == REGRESSED
        ]

    def critical(self, candidate_run: str) -> list:
        """The subset of regressions(candidate_run) severe enough to block acceptance."""
        return [
            regression
            for regression in self.regressions(candidate_run)
            if regression.severity == SEVERITY_CRITICAL
        ]
