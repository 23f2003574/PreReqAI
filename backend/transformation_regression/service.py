import ast
from datetime import datetime, timezone

from backend.api_candidates import LLMAPICandidateService
from backend.code_transformation import LLMCodeTransformationService
from backend.test_generation import INVALID, LLMTestGenerationService
from backend.transformation_diff import LLMTransformationDiffService
from backend.transformation_execution import LLMTransformationExecutionService
from backend.transformation_verification import LLMTransformationVerificationService

from .models import CRITICAL, MINOR, LLMTransformationRegression


class UnverifiedTransformationError(ValueError):
    """Raised when analyze() is called for an execution that hasn't passed
    Commit #6 syntax verification."""


class MissingBaselineError(ValueError):
    """Raised when no pre-transformation generated tests exist to compare
    the execution's behavior against."""


class UnknownRegressionAnalysisError(KeyError):
    """Raised when regressions()/critical() is called before analyze() for an execution_id."""


class UnknownRegressionError(KeyError):
    """Raised when resolve() is called for a regression_id that was never detected."""


def _call(fn, payload: dict) -> dict:
    try:
        return {"raised": False, "value": fn(**payload), "error": None}
    except Exception as exc:  # the notebook function is arbitrary, already-approved user code
        return {"raised": True, "value": None, "error": f"{type(exc).__name__}: {exc}"}


def _load_function(source: str, function_name: str):
    namespace: dict = {}
    exec(source, namespace)  # already-applied, human-approved notebook source (Commit #4/#5 gates)
    return namespace[function_name]


def _function_names(source: str) -> set:
    return {node.name for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}


class LLMTransformationRegressionService:
    """Detects behavioral regressions between a function's pre- and
    post-transformation behavior, before its execution may be released.

    Reuses LLMTransformationVerificationService.syntax() as the sole gate
    -- analyze() never runs a transformation that hasn't passed Commit #6
    syntax verification -- and backend.test_generation's already-generated
    tests (from the original notebook-to-API series) purely for their
    `input` values. Unlike every earlier commit in this codebase, analyze()
    actually calls both the original_source and applied_source functions
    Commit #5 already preserved on the execution, because a regression is
    fundamentally a behavioral comparison and there is no way to detect one
    without observing real behavior; both are already-applied,
    human-approved notebook source (the Commit #4 approval gate), so this
    is the same trust boundary as running the notebook itself. analyze()
    only ever reads the execution, verification, and existing
    candidates/tests -- it never mutates notebook source, and resolve()
    never fixes a regression, only acknowledges it.
    """

    def __init__(
        self,
        verification_service: LLMTransformationVerificationService,
        execution_service: LLMTransformationExecutionService,
        diff_service: LLMTransformationDiffService,
        transformation_service: LLMCodeTransformationService,
        api_candidate_service: LLMAPICandidateService,
        test_generation_service: LLMTestGenerationService,
    ):
        self._verification_service = verification_service
        self._execution_service = execution_service
        self._diff_service = diff_service
        self._transformation_service = transformation_service
        self._api_candidate_service = api_candidate_service
        self._test_generation_service = test_generation_service
        self._regressions_by_execution = {}
        self._regressions_by_id = {}
        self._resolved_ids = set()
        self._regression_counter = 0

    def analyze(self, execution_id: str) -> list:
        if not self._verification_service.syntax(execution_id):
            raise UnverifiedTransformationError(
                f"execution {execution_id!r} has not passed syntax verification"
            )

        execution = self._execution_service.get(execution_id)
        diff = self._diff_service.get(execution.diff_id)
        plan = self._transformation_service.get(diff.plan_id)
        candidates_by_function = {
            candidate.function_name: candidate
            for candidate in self._api_candidate_service.candidates(plan.notebook_id)
        }

        regressions = []
        baseline_found = False

        for applied in execution.applied_cells:
            common_names = _function_names(applied["original_source"]) & _function_names(
                applied["applied_source"]
            )

            for function_name in common_names:
                candidate = candidates_by_function.get(function_name)
                if candidate is None:
                    continue

                generated_tests = self._test_generation_service.tests(candidate.candidate_id)
                if not generated_tests:
                    continue

                baseline_found = True
                original_fn = _load_function(applied["original_source"], function_name)
                transformed_fn = _load_function(applied["applied_source"], function_name)

                for test in generated_tests:
                    expected = _call(original_fn, test.input)
                    actual = _call(transformed_fn, test.input)

                    if test.category == INVALID:
                        if expected["raised"] == actual["raised"]:
                            continue
                        severity = MINOR
                    else:
                        if expected == actual:
                            continue
                        severity = CRITICAL

                    self._regression_counter += 1
                    regression = LLMTransformationRegression(
                        regression_id=f"regression-{execution_id}-{self._regression_counter}",
                        execution_id=execution_id,
                        test_id=test.test_id,
                        expected=expected,
                        actual=actual,
                        severity=severity,
                        detected_at=datetime.now(timezone.utc),
                    )
                    regressions.append(regression)
                    self._regressions_by_id[regression.regression_id] = regression

        if not baseline_found:
            raise MissingBaselineError(
                f"no pre-transformation generated tests were found to compare "
                f"execution {execution_id!r} against"
            )

        self._regressions_by_execution[execution_id] = regressions
        return list(regressions)

    def _tracked(self, execution_id: str) -> list:
        try:
            return self._regressions_by_execution[execution_id]
        except KeyError:
            raise UnknownRegressionAnalysisError(execution_id)

    def regressions(self, execution_id: str) -> list:
        return [r for r in self._tracked(execution_id) if r.regression_id not in self._resolved_ids]

    def critical(self, execution_id: str) -> bool:
        return any(r.severity == CRITICAL for r in self.regressions(execution_id))

    def resolve(self, regression_id: str) -> bool:
        if regression_id not in self._regressions_by_id:
            raise UnknownRegressionError(regression_id)
        self._resolved_ids.add(regression_id)
        return True
