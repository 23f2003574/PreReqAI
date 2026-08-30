from datetime import datetime, timezone

from ..evaluation_baselines import LLMEvaluationBaselineService, UnknownEvaluationBaselineError
from ..evaluation_criteria import LLMEvaluationCriteriaService
from ..evaluation_dataset_runs import LLMEvaluationDatasetRunService
from ..evaluation_datasets import LLMEvaluationDatasetService
from ..evaluation_regressions import LLMEvaluationRegressionService
from ..evaluation_runs import SUCCEEDED
from ..evaluation_thresholds import LLMEvaluationThresholdService, UnknownEvaluationThresholdError
from .models import ACCEPTED, REJECTED, LLMEvaluationGate


class LLMEvaluationGateService:
    """The one accept/reject gate for a Commit #9 dataset run, from existing judgments.

    Reuses Commit #5's thresholds, Commit #10's regression detection, and
    Commit #11's active baseline lookup end to end -- no new scoring or
    comparison logic, only orchestration of what those services already
    compute into one set of findings and one verdict. evaluate() always
    recomputes fresh from current data, so repeated calls are deterministic
    by construction rather than by caching.
    """

    def __init__(
        self,
        dataset_run_service: LLMEvaluationDatasetRunService,
        dataset_service: LLMEvaluationDatasetService,
        criteria_service: LLMEvaluationCriteriaService,
        threshold_service: LLMEvaluationThresholdService,
        regression_service: LLMEvaluationRegressionService,
        baseline_service: LLMEvaluationBaselineService,
    ):
        self._dataset_run_service = dataset_run_service
        self._dataset_service = dataset_service
        self._criteria_service = criteria_service
        self._threshold_service = threshold_service
        self._regression_service = regression_service
        self._baseline_service = baseline_service
        self._gates = {}
        self._counter = 0

    @staticmethod
    def _check_completed(case_runs: list):
        if not case_runs:
            return False, "dataset run has no case runs"
        failed = [run.run_id for run in case_runs if run.status != SUCCEEDED]
        if failed:
            return False, f"case run(s) did not succeed: {failed}"
        return True, "every case run succeeded"

    def _enabled_thresholds(self, task_type: str) -> dict:
        """{criterion_id: threshold} for every enabled threshold configured for task_type."""
        configured = {}
        for criterion in self._criteria_service.list(task_type=task_type):
            try:
                threshold = self._threshold_service.get(criterion.criterion_id)
            except UnknownEvaluationThresholdError:
                continue
            if threshold.enabled:
                configured[criterion.criterion_id] = threshold
        return configured

    def _check_thresholds_configured(self, task_type: str):
        configured = self._enabled_thresholds(task_type)
        if not configured:
            return False, f"no enabled threshold is configured for task_type {task_type!r}"
        return True, f"{len(configured)} enabled threshold(s) configured for {task_type!r}"

    def _check_thresholds_passed(self, case_runs: list):
        """Reuses Commit #5's passed(): a required criterion whose score has gone
        missing (e.g. disabled after its threshold was set) already fails here --
        Commit #5's own "missing required scores -> not passed" rule -- so a
        second, separate coverage check would only duplicate it."""
        failing = [run.run_id for run in case_runs if not self._threshold_service.passed(run.run_id)]
        if failing:
            return False, f"case run(s) failed their configured thresholds: {failing}"
        return True, "every case run passed its configured thresholds"

    def _check_baseline_regression(self, dataset_id: str, case_runs: list):
        try:
            baseline = self._baseline_service.get(dataset_id)
        except UnknownEvaluationBaselineError:
            return True, "no active baseline is configured for this dataset yet"

        baseline_dataset_run = self._dataset_run_service.get(baseline.run_id)
        baseline_by_case = {
            run.case_id: run.run_id
            for run in self._dataset_run_service.case_runs(baseline_dataset_run.dataset_run_id)
        }

        blocking = []
        for run in case_runs:
            baseline_run_id = baseline_by_case.get(run.case_id)
            if baseline_run_id is None:
                continue
            self._regression_service.analyze(baseline_run_id, run.run_id)
            if self._regression_service.critical(run.run_id):
                blocking.append(run.run_id)

        if blocking:
            return False, f"critical regression against the active baseline for run(s): {blocking}"
        return True, "no blocking regression against the active baseline"

    def evaluate(self, run_id: str) -> LLMEvaluationGate:
        dataset_run = self._dataset_run_service.get(run_id)
        case_runs = self._dataset_run_service.case_runs(run_id)
        task_type = self._dataset_service.get(dataset_run.dataset_id).task_type

        findings = []

        def add(check: str, passed: bool, detail: str):
            findings.append({"check": check, "passed": passed, "detail": detail})

        completed_ok, completed_detail = self._check_completed(case_runs)
        add("completed_run", completed_ok, completed_detail)

        configured_ok, configured_detail = self._check_thresholds_configured(task_type)
        add("thresholds_configured", configured_ok, configured_detail)

        if completed_ok:
            add("thresholds_passed", *self._check_thresholds_passed(case_runs))
            add("baseline_regression", *self._check_baseline_regression(dataset_run.dataset_id, case_runs))
        else:
            skipped = "skipped: the run did not complete"
            add("thresholds_passed", False, skipped)
            add("baseline_regression", False, skipped)

        status = ACCEPTED if all(finding["passed"] for finding in findings) else REJECTED

        self._counter += 1
        gate = LLMEvaluationGate(
            gate_id=f"eval-gate-{self._counter}",
            run_id=run_id,
            status=status,
            findings=findings,
            evaluated_at=datetime.now(timezone.utc),
        )
        gate.validate()

        self._gates[gate.gate_id] = gate
        return gate

    def findings(self, run_id: str) -> list:
        return self.evaluate(run_id).findings

    def passed(self, run_id: str) -> bool:
        return self.evaluate(run_id).status == ACCEPTED
