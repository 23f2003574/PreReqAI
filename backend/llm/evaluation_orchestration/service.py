import dataclasses
from datetime import datetime, timezone

from ..evaluation_baselines import LLMEvaluationBaselineService, UnknownEvaluationBaselineError
from ..evaluation_dataset_runs import LLMEvaluationDatasetRunService
from ..evaluation_gates import ACCEPTED as GATE_ACCEPTED
from ..evaluation_gates import LLMEvaluationGateService
from ..evaluation_regressions import LLMEvaluationRegressionService
from ..evaluation_runs import SUCCEEDED
from ..evaluation_scoring import LLMEvaluationScoringService
from .models import ACCEPTED, PASSED, REJECTED, LLMEvaluationDecision


class GateNotPassedError(ValueError):
    """Raised when accept() is called for a dataset run whose gate did not pass."""


class UnknownEvaluationDecisionError(KeyError):
    """Raised when looking up a dataset_run_id that was never evaluate()'d."""


class LLMEvaluationOrchestrationService:
    """The single entrypoint tying Commits #1-#12 into one deterministic workflow.

    evaluate() runs a dataset through Commit #9's existing execution
    pipeline, then Commit #12's gate (itself built on Commit #4's scores,
    Commit #5's thresholds, and Commit #10's regressions against Commit
    #11's active baseline) -- no new execution, scoring, or comparison
    logic is added here, only the sequencing and one resulting decision.
    Only accept() ever touches the active baseline, and only when the
    caller names the exact dataset_run_id to promote -- evaluate() never
    replaces a baseline on its own.
    """

    def __init__(
        self,
        dataset_run_service: LLMEvaluationDatasetRunService,
        scoring_service: LLMEvaluationScoringService,
        gate_service: LLMEvaluationGateService,
        baseline_service: LLMEvaluationBaselineService,
        regression_service: LLMEvaluationRegressionService,
    ):
        self._dataset_run_service = dataset_run_service
        self._scoring_service = scoring_service
        self._gate_service = gate_service
        self._baseline_service = baseline_service
        self._regression_service = regression_service
        self._decisions = {}
        self._counter = 0

    def _aggregate_score(self, case_runs: list):
        """The mean overall() across every case run that succeeded -- None,
        never a fabricated zero, when nothing succeeded to score."""
        succeeded_scores = [
            self._scoring_service.overall(run.run_id) for run in case_runs if run.status == SUCCEEDED
        ]
        if not succeeded_scores:
            return None
        return round(sum(succeeded_scores) / len(succeeded_scores), 6)

    def _active_baseline_id(self, dataset_id: str):
        try:
            return self._baseline_service.get(dataset_id).baseline_id
        except UnknownEvaluationBaselineError:
            return None

    def evaluate(self, dataset_id: str, provider: str, model: str) -> LLMEvaluationDecision:
        """Run dataset_id through Commit #9 with provider/model, then gate the result."""
        dataset_run = self._dataset_run_service.run(dataset_id, provider=provider, model=model)
        gate = self._gate_service.evaluate(dataset_run.dataset_run_id)

        case_runs = self._dataset_run_service.case_runs(dataset_run.dataset_run_id)
        blocking_findings = [finding for finding in gate.findings if not finding["passed"]]
        status = PASSED if gate.status == GATE_ACCEPTED else REJECTED

        self._counter += 1
        decision = LLMEvaluationDecision(
            decision_id=f"eval-decision-{self._counter}",
            dataset_run_id=dataset_run.dataset_run_id,
            provider=dataset_run.provider,
            model=dataset_run.model,
            status=status,
            score=self._aggregate_score(case_runs),
            blocking_findings=blocking_findings,
            baseline_id=self._active_baseline_id(dataset_id),
            created_at=datetime.now(timezone.utc),
        )
        decision.validate()

        self._decisions[dataset_run.dataset_run_id] = decision
        return decision

    def compare(self, dataset_run_id: str, baseline: str) -> dict:
        """Commit #10 regressions between dataset_run_id and another dataset_run_id
        (baseline), matched case by case. Purely read-only reporting."""
        candidate_case_runs = self._dataset_run_service.case_runs(dataset_run_id)
        baseline_dataset_run = self._dataset_run_service.get(baseline)
        baseline_by_case = {
            run.case_id: run.run_id
            for run in self._dataset_run_service.case_runs(baseline_dataset_run.dataset_run_id)
        }

        results = {}
        for run in candidate_case_runs:
            baseline_run_id = baseline_by_case.get(run.case_id)
            if baseline_run_id is None:
                continue
            results[run.case_id] = self._regression_service.analyze(baseline_run_id, run.run_id)
        return results

    def accept(self, dataset_run_id: str) -> LLMEvaluationDecision:
        """Explicitly promote dataset_run_id to be its dataset's baseline.

        Requires evaluate() to have already produced a PASSED decision for
        it -- a REJECTED or not-yet-evaluated run is refused, and calling
        this is the only way a baseline is ever created or replaced.
        """
        decision = self.decision(dataset_run_id)
        if decision.status != PASSED:
            raise GateNotPassedError(
                f"dataset run {dataset_run_id!r} has status {decision.status!r}; only a "
                "run whose gate passed may become a baseline"
            )

        dataset_run = self._dataset_run_service.get(dataset_run_id)
        try:
            self._baseline_service.get(dataset_run.dataset_id)
        except UnknownEvaluationBaselineError:
            baseline = self._baseline_service.accept(dataset_run_id)
        else:
            baseline = self._baseline_service.replace(dataset_run.dataset_id, dataset_run_id)

        accepted = dataclasses.replace(decision, status=ACCEPTED, baseline_id=baseline.baseline_id)
        accepted.validate()

        self._decisions[dataset_run_id] = accepted
        return accepted

    def decision(self, dataset_run_id: str) -> LLMEvaluationDecision:
        try:
            return self._decisions[dataset_run_id]
        except KeyError:
            raise UnknownEvaluationDecisionError(dataset_run_id)
