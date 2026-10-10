from ..evaluation_criteria import LLMEvaluationCriteriaService
from ..evaluation_scoring import LLMEvaluationScoringService
from .models import LLMEvaluationThreshold


class UnknownEvaluationThresholdError(KeyError):
    """Raised when looking up a criterion_id with no threshold configured."""


class LLMEvaluationThresholdService:
    """Pass/fail quality bars for Commit #3 criteria, checked against Commit #4 scores.

    Reuses Commit #3's LLMEvaluationCriteriaService for what a criterion is
    and whether it is required, and Commit #4's LLMEvaluationScoringService
    for the actual scores -- no second scoring system, and no ranking of
    providers/models here, only whether one run's already-computed scores
    clear the bars configured for their criteria.
    """

    def __init__(
        self,
        criteria_service: LLMEvaluationCriteriaService,
        scoring_service: LLMEvaluationScoringService,
    ):
        self._criteria_service = criteria_service
        self._scoring_service = scoring_service
        self._thresholds = {}

    def set(self, criterion_id: str, minimum_score: float) -> LLMEvaluationThreshold:
        """Create or replace the threshold for criterion_id. The criterion must exist."""
        self._criteria_service.get(criterion_id)

        existing = self._thresholds.get(criterion_id)
        threshold = LLMEvaluationThreshold(
            threshold_id=existing.threshold_id if existing else f"threshold-{criterion_id}",
            criterion_id=criterion_id,
            minimum_score=minimum_score,
            enabled=existing.enabled if existing else True,
        )
        threshold.validate()

        self._thresholds[criterion_id] = threshold
        return threshold

    def get(self, criterion_id: str) -> LLMEvaluationThreshold:
        try:
            return self._thresholds[criterion_id]
        except KeyError:
            raise UnknownEvaluationThresholdError(criterion_id)

    def enable(self, criterion_id: str) -> LLMEvaluationThreshold:
        threshold = self.get(criterion_id)
        threshold.enabled = True
        return threshold

    def disable(self, criterion_id: str) -> LLMEvaluationThreshold:
        threshold = self.get(criterion_id)
        threshold.enabled = False
        return threshold

    def evaluate(self, run_id: str) -> list:
        """Per-criterion pass/fail for every enabled threshold, against the run's scores.

        A disabled threshold imposes no requirement and is left out entirely
        -- not merely marked passed. A criterion with an enabled threshold
        but no score for this run (e.g. it was disabled after being scored,
        or was never scored at all) is reported with score=None and
        passed=False -- a missing score is never treated as a pass.
        """
        scores_by_criterion = {
            score.criterion_id: score.score for score in self._scoring_service.score(run_id)
        }

        results = []
        for threshold in self._thresholds.values():
            if not threshold.enabled:
                continue

            criterion = self._criteria_service.get(threshold.criterion_id)
            score = scores_by_criterion.get(threshold.criterion_id)
            passed = score is not None and score >= threshold.minimum_score

            results.append(
                {
                    "criterion_id": threshold.criterion_id,
                    "required": criterion.required,
                    "minimum_score": threshold.minimum_score,
                    "score": score,
                    "passed": passed,
                }
            )

        return sorted(results, key=lambda result: result["criterion_id"])

    def failures(self, run_id: str) -> list:
        """The required, enabled thresholds this run did not clear.

        These are exactly what determine passed() -- an optional criterion
        missing or below its threshold is visible in evaluate() but never
        appears here and never blocks an overall pass.
        """
        return [
            result
            for result in self.evaluate(run_id)
            if result["required"] and not result["passed"]
        ]

    def passed(self, run_id: str) -> bool:
        """Overall pass: every enabled, required threshold was cleared."""
        return not self.failures(run_id)
