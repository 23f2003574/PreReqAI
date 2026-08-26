from datetime import datetime, timezone

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_compatibility_review import LLMCodePatchCompatibilityService
from backend.code_patch_execution import LLMCodePatchExecutionService
from backend.code_patch_gate import FAILED as GATE_FAILED
from backend.code_patch_gate import LLMCodePatchGateService
from backend.code_patch_planning import LLMCodePatchService
from backend.code_patch_quality_review import LLMCodePatchQualityService
from backend.code_patch_regression import LLMCodePatchRegressionService, MissingBaselineError
from backend.code_patch_release import LLMCodePatchReleaseService
from backend.code_patch_security_review import LLMCodePatchSecurityService
from backend.code_patch_validation import LLMCodePatchValidationService
from backend.code_patch_verification import LLMCodePatchVerificationService
from backend.generated_code_review import LLMGeneratedCodeReviewService

from .models import APPLIED, READY_FOR_RELEASE, REJECTED, RELEASED, ROLLED_BACK, LLMCodePatchDecision


class NoFixSuggestionAvailableError(ValueError):
    """Raised when prepare_patch() is called for a review with no fix suggestions to plan from."""


class NotReadyForReleaseError(ValueError):
    """Raised when release() is called for an execution whose decision isn't READY_FOR_RELEASE."""


class UnknownDecisionError(KeyError):
    """Raised when decision()/release() is called for an execution_id with no recorded decision."""


class LLMCodePatchOrchestrationService:
    """Unifies Commits #1-#12 into one safe review -> patch -> release pipeline.

    Every stage is a direct call into the service that already owns it --
    review() only calls Commit #1's own review(), prepare_patch() only
    calls Commit #2's suggest() and Commit #3's plan(), apply() only calls
    Commit #4's validate() and then Commit #5's apply() (never applying an
    invalid plan), verify() only calls Commit #6 verification, Commit #7
    regression analysis, Commit #8 security review, Commit #9 compatibility
    review, Commit #10 quality review, and Commit #11's release gates, in
    that order -- rolling back (via Commit #5) at the first blocking
    failure so a rejected patch never lingers half-applied -- and release()
    only ever calls Commit #12's prepare() once verify() has already
    recorded READY_FOR_RELEASE. Nothing here reimplements a single check
    any earlier commit already performs, and nothing here touches the
    compiler directly. Exactly one LLMCodePatchDecision is kept per
    execution_id, replaced (never appended) at each stage, so
    decision(execution_id) is always the one deterministic, current
    verdict.
    """

    def __init__(
        self,
        review_service: LLMGeneratedCodeReviewService,
        fix_service: LLMCodeFixSuggestionService,
        patch_service: LLMCodePatchService,
        validation_service: LLMCodePatchValidationService,
        execution_service: LLMCodePatchExecutionService,
        verification_service: LLMCodePatchVerificationService,
        regression_service: LLMCodePatchRegressionService,
        security_service: LLMCodePatchSecurityService,
        compatibility_service: LLMCodePatchCompatibilityService,
        quality_service: LLMCodePatchQualityService,
        gate_service: LLMCodePatchGateService,
        release_service: LLMCodePatchReleaseService,
    ):
        self._review_service = review_service
        self._fix_service = fix_service
        self._patch_service = patch_service
        self._validation_service = validation_service
        self._execution_service = execution_service
        self._verification_service = verification_service
        self._regression_service = regression_service
        self._security_service = security_service
        self._compatibility_service = compatibility_service
        self._quality_service = quality_service
        self._gate_service = gate_service
        self._release_service = release_service
        self._decisions = {}
        self._decision_counter = 0

    def _store_decision(
        self,
        execution_id,
        status: str,
        reason: str,
        blocking_findings=(),
        release_candidate_id: str = None,
    ) -> LLMCodePatchDecision:
        self._decision_counter += 1
        key = execution_id if execution_id is not None else f"rejected-{self._decision_counter}"
        decision = LLMCodePatchDecision(
            decision_id=f"decision-{key}-{self._decision_counter}",
            execution_id=execution_id,
            status=status,
            release_candidate_id=release_candidate_id,
            blocking_findings=list(blocking_findings),
            reason=reason,
            created_at=datetime.now(timezone.utc),
        )
        if execution_id is not None:
            self._decisions[execution_id] = decision
        return decision

    def review(self, generated_output):
        return self._review_service.review(generated_output)

    def prepare_patch(self, review_id: str):
        suggestions = self._fix_service.suggest(review_id)
        if not suggestions:
            raise NoFixSuggestionAvailableError(f"review {review_id!r} produced no fix suggestions to plan from")
        return self._patch_service.plan(suggestions[0].suggestion_id)

    def apply(self, plan_id: str) -> LLMCodePatchDecision:
        validation = self._validation_service.validate(plan_id)
        if not validation.valid:
            blocking = [finding["category"] for finding in validation.findings if finding["blocking"]]
            return self._store_decision(None, REJECTED, "patch failed validation", blocking_findings=blocking)

        execution = self._execution_service.apply(plan_id)
        return self._store_decision(execution.execution_id, APPLIED, "patch applied; pending verification")

    def _rolled_back(self, execution_id: str, reason: str, blocking_findings=()) -> LLMCodePatchDecision:
        self._execution_service.rollback(execution_id)
        return self._store_decision(execution_id, ROLLED_BACK, reason, blocking_findings=blocking_findings)

    def verify(self, execution_id: str) -> LLMCodePatchDecision:
        self._verification_service.verify(execution_id)
        if self._verification_service.blocking(execution_id):
            return self._rolled_back(execution_id, "verification failed", blocking_findings=["VERIFICATION"])

        try:
            self._regression_service.analyze(execution_id)
        except MissingBaselineError:
            pass
        else:
            if self._regression_service.critical(execution_id):
                return self._rolled_back(execution_id, "regression detected", blocking_findings=["REGRESSION"])

        self._security_service.analyze(execution_id)
        if self._security_service.blocking(execution_id):
            return self._rolled_back(execution_id, "security review failed", blocking_findings=["SECURITY"])

        self._compatibility_service.review(execution_id)
        if not self._compatibility_service.compatible(execution_id):
            return self._rolled_back(execution_id, "compatibility review failed", blocking_findings=["COMPATIBILITY"])

        self._quality_service.analyze(execution_id)
        if self._quality_service.blocking(execution_id):
            return self._rolled_back(execution_id, "quality review failed", blocking_findings=["QUALITY"])

        gates = self._gate_service.evaluate(execution_id)
        if not self._gate_service.passed(execution_id):
            failing = sorted({gate.gate_type for gate in gates if gate.status == GATE_FAILED})
            return self._rolled_back(execution_id, f"gates failed: {', '.join(failing)}", blocking_findings=failing)

        return self._store_decision(execution_id, READY_FOR_RELEASE, "all checks passed")

    def _get(self, execution_id: str) -> LLMCodePatchDecision:
        try:
            return self._decisions[execution_id]
        except KeyError:
            raise UnknownDecisionError(execution_id)

    def release(self, execution_id: str) -> LLMCodePatchDecision:
        decision = self._get(execution_id)
        if decision.status != READY_FOR_RELEASE:
            raise NotReadyForReleaseError(
                f"execution {execution_id!r} is not ready for release (status={decision.status!r})"
            )

        candidate = self._release_service.prepare(execution_id)
        return self._store_decision(
            execution_id, RELEASED, "release candidate created", release_candidate_id=candidate.candidate_id
        )

    def rollback(self, execution_id: str) -> LLMCodePatchDecision:
        return self._rolled_back(execution_id, "manually rolled back")

    def decision(self, execution_id: str) -> LLMCodePatchDecision:
        return self._get(execution_id)
