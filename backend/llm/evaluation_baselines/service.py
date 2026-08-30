from datetime import datetime, timezone

from ..evaluation_dataset_runs import LLMEvaluationDatasetRunService
from ..evaluation_regressions import LLMEvaluationRegressionService
from ..evaluation_runs import SUCCEEDED
from ..evaluation_scoring import LLMEvaluationScoringService
from ..evaluation_thresholds import LLMEvaluationThresholdService
from .models import ACTIVE, SUPERSEDED, InvalidEvaluationBaselineError, LLMEvaluationBaseline


class IncompleteEvaluationRunError(ValueError):
    """Raised when a dataset run has no case runs, or one that did not succeed."""


class ThresholdFailureError(ValueError):
    """Raised when a case run in the dataset run fails its configured thresholds."""


class RegressedBaselineRunError(ValueError):
    """Raised when a run critically regresses against the dataset's current baseline."""


class DuplicateBaselineError(ValueError):
    """Raised when accept() is called for a dataset that already has an active baseline."""


class UnknownEvaluationBaselineError(KeyError):
    """Raised when looking up a dataset_id with no active baseline."""


class LLMEvaluationBaselineService:
    """The explicit, human-in-the-loop gate for accepting a Commit #9 dataset run as truth.

    Reuses Commit #9's dataset runs, Commit #4's scores, Commit #5's
    thresholds, and Commit #10's regression detection end to end -- no new
    benchmark or scoring system. Nothing here ever picks a baseline on its
    own: accept()/replace() only act on the exact run_id the caller names.
    """

    def __init__(
        self,
        dataset_run_service: LLMEvaluationDatasetRunService,
        scoring_service: LLMEvaluationScoringService,
        threshold_service: LLMEvaluationThresholdService,
        regression_service: LLMEvaluationRegressionService,
    ):
        self._dataset_run_service = dataset_run_service
        self._scoring_service = scoring_service
        self._threshold_service = threshold_service
        self._regression_service = regression_service
        self._baselines = {}
        self._active_by_dataset = {}
        self._counter = 0

    def _completed_case_runs(self, dataset_run) -> list:
        case_runs = self._dataset_run_service.case_runs(dataset_run.dataset_run_id)
        if not case_runs:
            raise IncompleteEvaluationRunError(
                f"dataset run {dataset_run.dataset_run_id!r} has no case runs"
            )
        for run in case_runs:
            if run.status != SUCCEEDED:
                raise IncompleteEvaluationRunError(
                    f"case run {run.run_id!r} (case {run.case_id!r}) did not succeed"
                )
        return case_runs

    def _require_thresholds_pass(self, case_runs: list):
        for run in case_runs:
            if not self._threshold_service.passed(run.run_id):
                raise ThresholdFailureError(
                    f"case run {run.run_id!r} (case {run.case_id!r}) failed its "
                    "configured thresholds"
                )

    def _require_not_regressed(self, dataset_id: str, candidate_case_runs: list):
        active_id = self._active_by_dataset.get(dataset_id)
        if active_id is None:
            return

        baseline = self._baselines[active_id]
        baseline_dataset_run = self._dataset_run_service.get(baseline.run_id)
        baseline_by_case = {
            run.case_id: run.run_id
            for run in self._dataset_run_service.case_runs(baseline_dataset_run.dataset_run_id)
        }

        for run in candidate_case_runs:
            baseline_run_id = baseline_by_case.get(run.case_id)
            if baseline_run_id is None:
                continue

            self._regression_service.analyze(baseline_run_id, run.run_id)
            if self._regression_service.critical(run.run_id):
                raise RegressedBaselineRunError(
                    f"run {run.run_id!r} for case {run.case_id!r} critically regresses "
                    f"against the current baseline for dataset {dataset_id!r}"
                )

    def validate(self, run_id: str) -> float:
        """Whether Commit #9 dataset_run_id run_id may become its dataset's baseline.

        Raises the specific reason it may not; otherwise returns the run's
        aggregate overall_score (the mean of Commit #4's overall() across
        every case run). Purely a check -- nothing is accepted or mutated.
        """
        dataset_run = self._dataset_run_service.get(run_id)
        case_runs = self._completed_case_runs(dataset_run)
        self._require_thresholds_pass(case_runs)
        self._require_not_regressed(dataset_run.dataset_id, case_runs)

        overall_scores = [self._scoring_service.overall(run.run_id) for run in case_runs]
        return round(sum(overall_scores) / len(overall_scores), 6)

    def _create(self, dataset_run) -> LLMEvaluationBaseline:
        overall_score = self.validate(dataset_run.dataset_run_id)

        self._counter += 1
        baseline = LLMEvaluationBaseline(
            baseline_id=f"eval-baseline-{self._counter}",
            dataset_id=dataset_run.dataset_id,
            run_id=dataset_run.dataset_run_id,
            provider=dataset_run.provider,
            model=dataset_run.model,
            overall_score=overall_score,
            accepted_at=datetime.now(timezone.utc),
            status=ACTIVE,
        )
        baseline.validate()

        self._baselines[baseline.baseline_id] = baseline
        self._active_by_dataset[dataset_run.dataset_id] = baseline.baseline_id
        return baseline

    def accept(self, run_id: str) -> LLMEvaluationBaseline:
        """Accept run_id as the first baseline for its dataset.

        Refuses if that dataset already has an active baseline -- use
        replace() to supersede one explicitly.
        """
        dataset_run = self._dataset_run_service.get(run_id)
        if dataset_run.dataset_id in self._active_by_dataset:
            raise DuplicateBaselineError(
                f"dataset {dataset_run.dataset_id!r} already has an active baseline; "
                "use replace() to supersede it"
            )
        return self._create(dataset_run)

    def replace(self, dataset_id: str, run_id: str) -> LLMEvaluationBaseline:
        """Explicitly supersede dataset_id's current active baseline with run_id."""
        current_id = self._active_by_dataset.get(dataset_id)
        if current_id is None:
            raise UnknownEvaluationBaselineError(dataset_id)

        dataset_run = self._dataset_run_service.get(run_id)
        if dataset_run.dataset_id != dataset_id:
            raise InvalidEvaluationBaselineError(
                f"run {run_id!r} belongs to dataset {dataset_run.dataset_id!r}, not "
                f"{dataset_id!r}"
            )

        new_baseline = self._create(dataset_run)
        self._baselines[current_id].status = SUPERSEDED
        return new_baseline

    def get(self, dataset_id: str) -> LLMEvaluationBaseline:
        try:
            return self._baselines[self._active_by_dataset[dataset_id]]
        except KeyError:
            raise UnknownEvaluationBaselineError(dataset_id)
