from datetime import datetime, timezone

from ..evaluation_cases import LLMEvaluationCaseService
from ..evaluation_comparison import IncompatibleEvaluationCasesError
from ..evaluation_criteria import LLMEvaluationCriteriaService
from ..evaluation_runs import SUCCEEDED, LLMEvaluationRunService
from ..evaluation_scoring import LLMEvaluationScoringService
from .models import LLMEvaluationMatrix


class UnknownEvaluationMatrixError(KeyError):
    """Raised when looking up a matrix_id that was never built."""


class LLMEvaluationMatrixService:
    """Aggregates Commit #4 overall scores across providers/models for one task_type.

    Reuses Commit #1's cases, Commit #2's runs (provider/model identity),
    Commit #3's criteria, and Commit #4's scoring end to end -- no second
    provider registry and no new scoring math, only grouping and averaging
    what those services already compute. Nothing here changes routing: the
    matrix is read-only reporting over runs the caller already produced.
    """

    def __init__(
        self,
        run_service: LLMEvaluationRunService,
        case_service: LLMEvaluationCaseService,
        criteria_service: LLMEvaluationCriteriaService,
        scoring_service: LLMEvaluationScoringService,
    ):
        self._run_service = run_service
        self._case_service = case_service
        self._criteria_service = criteria_service
        self._scoring_service = scoring_service
        self._matrices = {}
        self._matrix_counter = 0

    @staticmethod
    def _aggregate(succeeded: list, excluded: list, key_fn) -> dict:
        groups = {}
        for entry in succeeded:
            group = groups.setdefault(key_fn(entry), {"overalls": [], "run_ids": [], "excluded_run_ids": []})
            group["overalls"].append(entry["overall"])
            group["run_ids"].append(entry["run_id"])
        for entry in excluded:
            group = groups.setdefault(key_fn(entry), {"overalls": [], "run_ids": [], "excluded_run_ids": []})
            group["excluded_run_ids"].append(entry["run_id"])

        return {
            key: {
                "overall": round(sum(group["overalls"]) / len(group["overalls"]), 6)
                if group["overalls"]
                else None,
                "run_count": len(group["overalls"]),
                "run_ids": list(group["run_ids"]),
                "excluded_run_ids": list(group["excluded_run_ids"]),
            }
            for key, group in groups.items()
        }

    def build(self, task_type: str, runs: list) -> LLMEvaluationMatrix:
        criteria = self._criteria_service.list(task_type=task_type)

        succeeded, excluded = [], []
        for run_id in runs:
            run = self._run_service.get(run_id)
            case = self._case_service.get(run.case_id)
            if case.task_type != task_type:
                raise IncompatibleEvaluationCasesError(
                    f"run {run_id!r} belongs to task_type {case.task_type!r}, not "
                    f"the matrix's {task_type!r}"
                )

            if run.status != SUCCEEDED:
                # Explicit exclusion: a run that did not succeed contributes no
                # score, and is never averaged in as a zero.
                excluded.append({"run_id": run_id, "provider": run.provider, "model": run.model})
                continue

            succeeded.append(
                {
                    "run_id": run_id,
                    "provider": run.provider,
                    "model": run.model,
                    "overall": self._scoring_service.overall(run_id),
                }
            )

        aggregate_scores = {
            "by_provider": self._aggregate(succeeded, excluded, key_fn=lambda e: e["provider"]),
            "by_model": self._aggregate(
                succeeded, excluded, key_fn=lambda e: (e["provider"], e["model"])
            ),
        }

        self._matrix_counter += 1
        matrix = LLMEvaluationMatrix(
            matrix_id=f"eval-matrix-{self._matrix_counter}",
            task_type=task_type,
            runs=list(runs),
            criteria=[criterion.criterion_id for criterion in criteria],
            aggregate_scores=aggregate_scores,
            generated_at=datetime.now(timezone.utc),
        )
        matrix.validate()

        self._matrices[matrix.matrix_id] = matrix
        return matrix

    def _get(self, matrix_id: str) -> LLMEvaluationMatrix:
        try:
            return self._matrices[matrix_id]
        except KeyError:
            raise UnknownEvaluationMatrixError(matrix_id)

    def provider_scores(self, matrix_id: str) -> dict:
        return self._get(matrix_id).aggregate_scores["by_provider"]

    def model_scores(self, matrix_id: str) -> dict:
        return self._get(matrix_id).aggregate_scores["by_model"]

    def best(self, matrix_id: str):
        """The (provider, model) with the highest aggregate overall score.

        None when nothing in the matrix ever succeeded. Ties break on
        provider then model name so the choice never depends on iteration
        or insertion order.
        """
        scored = [
            (provider, model, scores)
            for (provider, model), scores in self.model_scores(matrix_id).items()
            if scores["overall"] is not None
        ]
        if not scored:
            return None

        scored.sort(key=lambda item: (-item[2]["overall"], item[0] or "", item[1] or ""))
        provider, model, scores = scored[0]
        return {
            "provider": provider,
            "model": model,
            "overall": scores["overall"],
            "run_count": scores["run_count"],
        }
