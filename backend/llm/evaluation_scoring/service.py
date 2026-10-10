import json
from datetime import datetime, timezone

from ..evaluation_cases import LLMEvaluationCaseService
from ..evaluation_criteria import LLMEvaluationCriteriaService
from ..evaluation_runs import SUCCEEDED, LLMEvaluationRunService
from .models import LLMEvaluationScore


class RunNotSucceededError(ValueError):
    """Raised when scoring is attempted on a run that did not succeed."""


class NoCriteriaRegisteredError(ValueError):
    """Raised when a case's task_type has no enabled criteria to score against."""


class LLMEvaluationScoringService:
    """Scores a Commit #2 run's output against Commit #3's enabled criteria.

    Deterministic and structured throughout: a run's output is compared
    against its own Commit #1 case's expected_properties -- the only
    structured assertion this repository has for what a task's output
    should contain -- never against a second LLM call or an external
    evaluation service. Every enabled criterion registered for the case's
    task_type is scored against that same deterministic match and then
    weighted by the criterion's own weight in overall(); this commit does
    not rank providers, it only scores one run's output.
    """

    def __init__(
        self,
        run_service: LLMEvaluationRunService,
        case_service: LLMEvaluationCaseService,
        criteria_service: LLMEvaluationCriteriaService,
    ):
        self._run_service = run_service
        self._case_service = case_service
        self._criteria_service = criteria_service
        self._scores = {}
        self._score_counter = 0

    @staticmethod
    def _match_expected_properties(output: str, expected_properties: dict):
        """Deterministic match ratio of a run's output against a case's expected_properties.

        Parses output as JSON when possible and compares each expected key
        by value (a list expectation matches if it is a subset of the
        actual list); falls back to a plain substring check against the raw
        output when it is not JSON or the key is absent, so a non-JSON or
        partially-structured response still gets a deterministic result
        rather than an automatic failure.
        """
        try:
            parsed = json.loads(output)
        except (TypeError, ValueError):
            parsed = None

        matched, missing = [], []
        for key, expected_value in expected_properties.items():
            actual = parsed.get(key) if isinstance(parsed, dict) else None

            if actual is not None:
                if isinstance(expected_value, list):
                    ok = isinstance(actual, list) and all(item in actual for item in expected_value)
                else:
                    ok = actual == expected_value
            elif isinstance(expected_value, list):
                ok = all(str(item) in output for item in expected_value)
            else:
                ok = str(expected_value) in output

            (matched if ok else missing).append(key)

        total = len(expected_properties)
        score = len(matched) / total if total else 0.0
        rationale = (
            f"matched {len(matched)}/{total} expected propert"
            f"{'y' if total == 1 else 'ies'}: {matched or 'none'}; missing: {missing or 'none'}"
        )
        return round(score, 6), rationale

    def _require_succeeded_run(self, run_id: str):
        run = self._run_service.get(run_id)
        if run.status != SUCCEEDED:
            raise RunNotSucceededError(
                f"run {run_id!r} has status {run.status!r}; only a {SUCCEEDED} run can be scored"
            )
        return run

    def score_criterion(self, run_id: str, criterion_id: str) -> LLMEvaluationScore:
        """Score one run against one criterion, regardless of the criterion's enabled state."""
        run = self._require_succeeded_run(run_id)
        criterion = self._criteria_service.get(criterion_id)
        case = self._case_service.get(run.case_id)

        match_score, rationale = self._match_expected_properties(
            run.output, case.expected_properties
        )

        self._score_counter += 1
        score = LLMEvaluationScore(
            score_id=f"eval-score-{self._score_counter}",
            run_id=run_id,
            criterion_id=criterion_id,
            score=match_score,
            rationale=f"[{criterion.name}] {rationale}",
            evaluated_at=datetime.now(timezone.utc),
        )
        score.validate()

        self._scores[score.score_id] = score
        return score

    def score(self, run_id: str) -> list:
        """Score a run against every enabled criterion registered for its case's task_type."""
        run = self._require_succeeded_run(run_id)
        case = self._case_service.get(run.case_id)

        criteria = self._criteria_service.list(task_type=case.task_type)
        if not criteria:
            raise NoCriteriaRegisteredError(
                f"no enabled criteria registered for task_type {case.task_type!r}"
            )

        return [self.score_criterion(run_id, criterion.criterion_id) for criterion in criteria]

    def overall(self, run_id: str) -> float:
        """Weighted-average score across every enabled criterion for the run's task_type."""
        run = self._require_succeeded_run(run_id)
        case = self._case_service.get(run.case_id)
        criteria = {
            criterion.criterion_id: criterion
            for criterion in self._criteria_service.list(task_type=case.task_type)
        }

        scores = self.score(run_id)

        total_weight = sum(criteria[score.criterion_id].weight for score in scores)
        if total_weight == 0:
            return round(sum(score.score for score in scores) / len(scores), 6)

        weighted = sum(score.score * criteria[score.criterion_id].weight for score in scores)
        return round(weighted / total_weight, 6)
