import copy
from datetime import datetime, timezone

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_execution import LLMCodePatchExecutionService
from backend.code_patch_gate import LLMCodePatchGateService, UnknownGateEvaluationError
from backend.code_patch_planning import LLMCodePatchService
from backend.generated_code_review import LLMGeneratedCodeReviewService

from .models import INVALIDATED, PREPARED, LLMCodePatchReleaseCandidate


class GatesNotEvaluatedError(ValueError):
    """Raised when prepare() is called for an execution whose release gates were never evaluated."""


class GatesNotPassedError(ValueError):
    """Raised when prepare() is called for an execution that hasn't passed every required gate."""


class UnknownReleaseCandidateError(KeyError):
    """Raised when validate()/status() is called for a candidate_id that was never prepared."""


class LLMCodePatchReleaseService:
    """Prepares an immutable release candidate for an execution that has
    passed every Commit #11 gate.

    Reuses LLMCodePatchGateService.passed() as the sole readiness check --
    prepare() never creates a candidate for an execution whose gates were
    never evaluated or didn't all pass, and a failed check always raises
    rather than producing one, so a failed preparation can never become a
    candidate. The candidate's artifacts are a frozen snapshot of the
    exact, real CompilerJobResult.output (backend.compilation_execution)
    that was verified -- located via the same plan -> Commit #2 suggestion
    -> Commit #1 review chain every later commit already uses, never a new
    build/artifact format. validate() re-runs the same gate check and
    invalidates the candidate if it no longer holds, so a regression
    discovered after prepare() (e.g. the gates are re-evaluated and now
    fail) is reflected instead of silently ignored. This service never
    mutates the gates, the execution, or the generated output, and never
    deploys anything.
    """

    def __init__(
        self,
        gate_service: LLMCodePatchGateService,
        execution_service: LLMCodePatchExecutionService,
        patch_service: LLMCodePatchService,
        fix_service: LLMCodeFixSuggestionService,
        review_service: LLMGeneratedCodeReviewService,
    ):
        self._gate_service = gate_service
        self._execution_service = execution_service
        self._patch_service = patch_service
        self._fix_service = fix_service
        self._review_service = review_service
        self._candidates = {}
        self._version_counter_by_job = {}
        self._candidate_counter = 0

    def _require_gates_passed(self, execution_id: str) -> None:
        try:
            passed = self._gate_service.passed(execution_id)
        except UnknownGateEvaluationError as exc:
            raise GatesNotEvaluatedError(
                f"execution {execution_id!r} has not had its release gates evaluated"
            ) from exc

        if not passed:
            raise GatesNotPassedError(f"execution {execution_id!r} has not passed every required gate")

    def _resolve_artifacts(self, execution_id: str) -> dict:
        execution = self._execution_service.get(execution_id)
        plan = self._patch_service.get(execution.plan_id)
        suggestion = self._fix_service.get(plan.suggestion_id)
        review = self._review_service.get(suggestion.review_id)
        generated_output = self._review_service.get_generated_output(review.target)
        return {"job_id": review.target, "output": copy.deepcopy(generated_output.output)}

    def prepare(self, execution_id: str) -> LLMCodePatchReleaseCandidate:
        self._require_gates_passed(execution_id)

        artifacts = self._resolve_artifacts(execution_id)
        job_id = artifacts["job_id"]

        self._version_counter_by_job[job_id] = self._version_counter_by_job.get(job_id, 0) + 1
        version = f"{job_id}-v{self._version_counter_by_job[job_id]}"

        self._candidate_counter += 1
        candidate = LLMCodePatchReleaseCandidate(
            candidate_id=f"release-candidate-{execution_id}-{self._candidate_counter}",
            execution_id=execution_id,
            version=version,
            status=PREPARED,
            artifacts=artifacts,
            created_at=datetime.now(timezone.utc),
        )
        self._candidates[candidate.candidate_id] = candidate
        return candidate

    def _get(self, candidate_id: str) -> LLMCodePatchReleaseCandidate:
        try:
            return self._candidates[candidate_id]
        except KeyError:
            raise UnknownReleaseCandidateError(candidate_id)

    def validate(self, candidate_id: str) -> bool:
        candidate = self._get(candidate_id)

        try:
            self._require_gates_passed(candidate.execution_id)
        except (GatesNotEvaluatedError, GatesNotPassedError):
            if candidate.status != INVALIDATED:
                self._candidates[candidate_id] = LLMCodePatchReleaseCandidate(
                    candidate_id=candidate.candidate_id,
                    execution_id=candidate.execution_id,
                    version=candidate.version,
                    status=INVALIDATED,
                    artifacts=candidate.artifacts,
                    created_at=candidate.created_at,
                )
            return False

        return True

    def status(self, candidate_id: str) -> str:
        return self._get(candidate_id).status
