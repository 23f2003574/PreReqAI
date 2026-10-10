from datetime import datetime, timezone

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_execution import LLMCodePatchExecutionService
from backend.code_patch_planning import LLMCodePatchService
from backend.code_patch_verification import LLMCodePatchVerificationService
from backend.generated_code_review import CATEGORIES
from backend.generated_code_review import CRITICAL as FINDING_CRITICAL
from backend.generated_code_review import LLMGeneratedCodeReviewService, UnknownReviewError

from .models import CRITICAL, MINOR, LLMCodePatchRegression


class UnverifiedPatchError(ValueError):
    """Raised when analyze() is called for an execution that hasn't passed Commit #6 syntax verification."""


class MissingBaselineError(ValueError):
    """Raised when no pre-patch baseline review exists to compare the execution's behavior against."""


class UnknownRegressionAnalysisError(KeyError):
    """Raised when regressions()/critical() is called before analyze() for an execution_id."""


def _profile(findings: list, category: str) -> dict:
    matching = [finding for finding in findings if finding["category"] == category]
    return {"blocking": any(finding["severity"] == FINDING_CRITICAL for finding in matching), "count": len(matching)}


class LLMCodePatchRegressionService:
    """Detects behavioral regressions introduced by a Commit #5 applied patch,
    before its execution may be accepted.

    Reuses LLMCodePatchVerificationService.syntax() as the sole gate --
    analyze() never compares behavior for an execution that hasn't passed
    Commit #6 syntax verification -- and, for the comparison itself, the
    exact same "existing test" Commit #6 already established:
    backend.generated_code_review's own review pipeline, reused twice --
    once for the pre-patch baseline review already on record
    (suggestion.review_id, the pre-patch baseline this codebase already
    keeps), once run fresh against the current, already-patched generated
    output. A regression is a category (CORRECTNESS/SECURITY/QUALITY/
    COMPATIBILITY) whose finding profile got worse between those two
    reviews -- never a new, separate execution/behavioral framework, and
    never a mutation of the generated output, the execution, or anything
    upstream of it.
    """

    def __init__(
        self,
        verification_service: LLMCodePatchVerificationService,
        execution_service: LLMCodePatchExecutionService,
        patch_service: LLMCodePatchService,
        fix_service: LLMCodeFixSuggestionService,
        review_service: LLMGeneratedCodeReviewService,
    ):
        self._verification_service = verification_service
        self._execution_service = execution_service
        self._patch_service = patch_service
        self._fix_service = fix_service
        self._review_service = review_service
        self._regressions_by_execution = {}
        self._regression_counter = 0

    def analyze(self, execution_id: str) -> list:
        if not self._verification_service.syntax(execution_id):
            raise UnverifiedPatchError(f"execution {execution_id!r} has not passed syntax verification")

        execution = self._execution_service.get(execution_id)
        plan = self._patch_service.get(execution.plan_id)
        suggestion = self._fix_service.get(plan.suggestion_id)

        try:
            baseline_review = self._review_service.get(suggestion.review_id)
        except UnknownReviewError as exc:
            raise MissingBaselineError(
                f"no pre-patch baseline review exists for execution {execution_id!r}"
            ) from exc

        generated_output = self._review_service.get_generated_output(baseline_review.target)
        current_review = self._review_service.review(generated_output)

        baseline_findings = self._review_service.findings(baseline_review.review_id)
        current_findings = self._review_service.findings(current_review.review_id)

        regressions = []
        for category in sorted(CATEGORIES):
            expected = _profile(baseline_findings, category)
            actual = _profile(current_findings, category)
            if expected == actual:
                continue

            if actual["blocking"] and not expected["blocking"]:
                severity = CRITICAL
            elif actual["count"] > expected["count"]:
                severity = MINOR
            else:
                continue

            self._regression_counter += 1
            regressions.append(
                LLMCodePatchRegression(
                    regression_id=f"regression-{execution_id}-{self._regression_counter}",
                    execution_id=execution_id,
                    test_id=category,
                    expected=expected,
                    actual=actual,
                    severity=severity,
                    detected_at=datetime.now(timezone.utc),
                )
            )

        self._regressions_by_execution[execution_id] = regressions
        return list(regressions)

    def _tracked(self, execution_id: str) -> list:
        try:
            return self._regressions_by_execution[execution_id]
        except KeyError:
            raise UnknownRegressionAnalysisError(execution_id)

    def regressions(self, execution_id: str) -> list:
        return list(self._tracked(execution_id))

    def critical(self, execution_id: str) -> bool:
        return any(regression.severity == CRITICAL for regression in self.regressions(execution_id))
