from datetime import datetime, timezone

from ..evaluation_datasets import LLMEvaluationDatasetService
from ..evaluation_runs import LLMEvaluationRunService
from .models import COMPLETED, LLMEvaluationDatasetRun


class DisabledEvaluationDatasetError(ValueError):
    """Raised when run() is called for a dataset that is disabled."""


class UnknownEvaluationDatasetRunError(KeyError):
    """Raised when looking up a dataset_run_id that was never recorded."""


class LLMEvaluationDatasetRunService:
    """Executes an entire Commit #8 dataset through Commit #2's case execution.

    No new provider execution pipeline and no automatic model selection:
    every case is run through the exact same LLMEvaluationRunService.run()
    Commit #2 already exercises, forced onto the caller's chosen provider
    via LLMRouteRequest.preferred_provider -- routing itself is untouched.
    Reading the dataset's cases() (Commit #8) also locks that dataset
    version, so a benchmark run is exactly what later becomes immutable.
    """

    def __init__(
        self,
        dataset_service: LLMEvaluationDatasetService,
        run_service: LLMEvaluationRunService,
    ):
        self._dataset_service = dataset_service
        self._run_service = run_service
        self._dataset_runs = {}
        self._counter = 0

    def run(self, dataset_id: str, provider: str, model: str) -> LLMEvaluationDatasetRun:
        dataset = self._dataset_service.get(dataset_id)
        if not dataset.enabled:
            raise DisabledEvaluationDatasetError(f"dataset {dataset_id!r} is disabled")
        dataset.validate()

        eligible_cases = self._dataset_service.cases(dataset_id)

        self._counter += 1
        dataset_run_id = f"eval-dataset-run-{self._counter}"

        started_at = datetime.now(timezone.utc)
        case_run_ids = [
            self._run_service.run(case.case_id, preferred_provider=provider).run_id
            for case in eligible_cases
        ]
        completed_at = datetime.now(timezone.utc)

        dataset_run = LLMEvaluationDatasetRun(
            dataset_run_id=dataset_run_id,
            dataset_id=dataset_id,
            provider=provider,
            model=model,
            case_runs=case_run_ids,
            status=COMPLETED,
            started_at=started_at,
            completed_at=completed_at,
        )
        dataset_run.validate()

        self._dataset_runs[dataset_run_id] = dataset_run
        return dataset_run

    def _get(self, dataset_run_id: str) -> LLMEvaluationDatasetRun:
        try:
            return self._dataset_runs[dataset_run_id]
        except KeyError:
            raise UnknownEvaluationDatasetRunError(dataset_run_id)

    def get(self, dataset_run_id: str) -> LLMEvaluationDatasetRun:
        return self._get(dataset_run_id)

    def status(self, dataset_run_id: str) -> str:
        return self._get(dataset_run_id).status

    def case_runs(self, dataset_run_id: str) -> list:
        """The Commit #2 run record for every case_run_id, in dataset order."""
        dataset_run = self._get(dataset_run_id)
        return [self._run_service.get(run_id) for run_id in dataset_run.case_runs]
