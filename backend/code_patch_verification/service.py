import ast
from datetime import datetime, timezone

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_execution import SUCCEEDED as EXECUTION_SUCCEEDED
from backend.code_patch_execution import LLMCodePatchExecutionService
from backend.code_patch_planning import LLMCodePatchService
from backend.generated_code_review import LLMGeneratedCodeReviewService

from .models import LLMCodePatchVerification


class ExecutionNotAppliedError(ValueError):
    """Raised when verify() is called for an execution that isn't currently SUCCEEDED
    (i.e. it was never applied, or it has since been rolled back)."""


class UnknownPatchVerificationError(KeyError):
    """Raised when findings()/blocking() is called before verify() for an execution_id."""


def _blocking(category: str, target: str, message: str) -> dict:
    return {"category": category, "target": target, "message": message, "blocking": True}


def _advisory(category: str, target: str, message: str) -> dict:
    return {"category": category, "target": target, "message": message, "blocking": False}


def _syntax_findings(output: dict) -> list:
    findings = []
    for key, value in output.items():
        if key != "source" or not isinstance(value, str):
            continue
        try:
            ast.parse(value)
        except SyntaxError as exc:
            findings.append(_blocking("SYNTAX_ERROR", key, f"generated output does not parse: {exc}"))
    return findings


class LLMCodePatchVerificationService:
    """Verifies a Commit #5 applied execution before its patched generated
    output may be accepted as valid.

    Reuses LLMCodePatchExecutionService.get() (only a SUCCEEDED, i.e.
    currently-applied, execution can be verified -- one that was never
    applied or has since been rolled back is rejected) to locate the plan,
    and walks the same plan -> Commit #2 suggestion -> Commit #1 review
    chain every later commit already uses to find the live generated
    output. Syntax of every "source"-holding key is checked first via
    `ast`, the same convention used throughout this codebase; tests are
    skipped entirely if syntax fails. Once syntax passes, the "relevant
    existing/generated test" for generated output is Commit #1's own
    LLMGeneratedCodeReviewService -- run again against the current,
    already-patched output -- so a fix that didn't actually resolve a
    blocking problem (or introduced a new one) is caught by the same real
    validation pipeline that found it in the first place, never a second,
    parallel checker. Verification only ever reads the generated output;
    it never mutates it, the execution, or anything upstream of it.
    """

    def __init__(
        self,
        execution_service: LLMCodePatchExecutionService,
        review_service: LLMGeneratedCodeReviewService,
        fix_service: LLMCodeFixSuggestionService,
        patch_service: LLMCodePatchService,
    ):
        self._execution_service = execution_service
        self._review_service = review_service
        self._fix_service = fix_service
        self._patch_service = patch_service
        self._verifications = {}
        self._verification_counter = 0

    def _resolve_output(self, plan):
        suggestion = self._fix_service.get(plan.suggestion_id)
        review = self._review_service.get(suggestion.review_id)
        return self._review_service.get_generated_output(review.target)

    def _run_tests(self, generated_output) -> tuple:
        fresh_review = self._review_service.review(generated_output)
        if self._review_service.blocking(fresh_review.review_id):
            return False, [
                _blocking(
                    "TEST_FAILURE",
                    fresh_review.review_id,
                    "the generated output still has a blocking finding after applying this patch",
                )
            ]
        return True, []

    def verify(self, execution_id: str) -> LLMCodePatchVerification:
        execution = self._execution_service.get(execution_id)
        if execution.status != EXECUTION_SUCCEEDED:
            raise ExecutionNotAppliedError(
                f"execution {execution_id!r} is not an applied patch (status={execution.status!r})"
            )

        plan = self._patch_service.get(execution.plan_id)
        generated_output = self._resolve_output(plan)

        findings = _syntax_findings(generated_output.output)
        syntax_valid = not findings

        if syntax_valid:
            tests_passed, test_findings = self._run_tests(generated_output)
            findings.extend(test_findings)
        else:
            tests_passed = False
            findings.append(
                _advisory("TESTS_SKIPPED", execution_id, "tests were skipped because syntax validation failed")
            )

        self._verification_counter += 1
        verification = LLMCodePatchVerification(
            verification_id=f"patch-verification-{execution_id}-{self._verification_counter}",
            execution_id=execution_id,
            syntax_valid=syntax_valid,
            tests_passed=tests_passed,
            findings=findings,
            verified_at=datetime.now(timezone.utc),
        )
        self._verifications[execution_id] = verification
        return verification

    def _get(self, execution_id: str) -> LLMCodePatchVerification:
        try:
            return self._verifications[execution_id]
        except KeyError:
            raise UnknownPatchVerificationError(execution_id)

    def findings(self, execution_id: str) -> list:
        return list(self._get(execution_id).findings)

    def blocking(self, execution_id: str) -> bool:
        return any(finding["blocking"] for finding in self._get(execution_id).findings)

    def syntax(self, execution_id: str) -> bool:
        return self._get(execution_id).syntax_valid
