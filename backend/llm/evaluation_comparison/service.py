from datetime import datetime, timezone

from ..evaluation_cases import LLMEvaluationCaseService
from ..evaluation_runs import LLMEvaluationRunService
from ..evaluation_scoring import LLMEvaluationScoringService
from .models import BASELINE, CANDIDATE, TIE, LLMEvaluationComparison


class IncompatibleEvaluationCasesError(ValueError):
    """Raised when the two runs being compared belong to different task_types."""


class LLMEvaluationComparisonService:
    """Compares two completed runs using only their existing Commit #4 scores.

    Reuses Commit #1's cases, Commit #2's runs, and Commit #4's scoring
    service end to end -- no second scoring model, no provider/model
    ranking, and no mutation: every method here only reads through those
    services and returns a comparison of what they already computed.
    """

    def __init__(
        self,
        run_service: LLMEvaluationRunService,
        case_service: LLMEvaluationCaseService,
        scoring_service: LLMEvaluationScoringService,
    ):
        self._run_service = run_service
        self._case_service = case_service
        self._scoring_service = scoring_service
        self._comparisons = {}
        self._comparison_counter = 0

    def _task_type(self, run_id: str) -> str:
        run = self._run_service.get(run_id)
        return self._case_service.get(run.case_id).task_type

    def _require_compatible(self, baseline_run: str, candidate_run: str):
        baseline_type = self._task_type(baseline_run)
        candidate_type = self._task_type(candidate_run)
        if baseline_type != candidate_type:
            raise IncompatibleEvaluationCasesError(
                f"baseline run {baseline_run!r} (task_type={baseline_type!r}) is not "
                f"comparable with candidate run {candidate_run!r} "
                f"(task_type={candidate_type!r})"
            )

    def _scores_map(self, run_id: str) -> dict:
        """Completed-run enforcement lives in Commit #4's score(): a non-SUCCEEDED
        run raises RunNotSucceededError here, exactly as it would for a direct
        scoring call."""
        return {score.criterion_id: score.score for score in self._scoring_service.score(run_id)}

    @staticmethod
    def _delta_entry(criterion_id: str, baseline_score, candidate_score) -> dict:
        has_both = baseline_score is not None and candidate_score is not None
        return {
            "criterion_id": criterion_id,
            "baseline_score": baseline_score,
            "candidate_score": candidate_score,
            "delta": round(candidate_score - baseline_score, 6) if has_both else None,
        }

    def criterion_delta(self, baseline_run: str, candidate_run: str, criterion_id: str) -> dict:
        """One criterion's delta between two runs; missing on either side is None, not dropped."""
        self._require_compatible(baseline_run, candidate_run)

        baseline_scores = self._scores_map(baseline_run)
        candidate_scores = self._scores_map(candidate_run)
        return self._delta_entry(
            criterion_id, baseline_scores.get(criterion_id), candidate_scores.get(criterion_id)
        )

    def overall_delta(self, baseline_run: str, candidate_run: str) -> float:
        self._require_compatible(baseline_run, candidate_run)

        baseline_overall = self._scoring_service.overall(baseline_run)
        candidate_overall = self._scoring_service.overall(candidate_run)
        return round(candidate_overall - baseline_overall, 6)

    def compare(self, baseline_run: str, candidate_run: str) -> LLMEvaluationComparison:
        self._require_compatible(baseline_run, candidate_run)

        baseline_scores = self._scores_map(baseline_run)
        candidate_scores = self._scores_map(candidate_run)
        matched_criterion_ids = sorted(set(baseline_scores) | set(candidate_scores))

        criterion_deltas = {
            criterion_id: self._delta_entry(
                criterion_id, baseline_scores.get(criterion_id), candidate_scores.get(criterion_id)
            )
            for criterion_id in matched_criterion_ids
        }

        baseline_overall = self._scoring_service.overall(baseline_run)
        candidate_overall = self._scoring_service.overall(candidate_run)
        overall_delta = round(candidate_overall - baseline_overall, 6)

        if candidate_overall > baseline_overall:
            winner = CANDIDATE
        elif baseline_overall > candidate_overall:
            winner = BASELINE
        else:
            winner = TIE

        self._comparison_counter += 1
        comparison = LLMEvaluationComparison(
            comparison_id=f"eval-comparison-{self._comparison_counter}",
            baseline_run=baseline_run,
            candidate_run=candidate_run,
            criterion_deltas=criterion_deltas,
            overall_delta=overall_delta,
            winner=winner,
            created_at=datetime.now(timezone.utc),
        )
        comparison.validate()

        self._comparisons[comparison.comparison_id] = comparison
        return comparison
