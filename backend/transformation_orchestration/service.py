from datetime import datetime, timezone

from backend.code_transformation import LLMCodeTransformationService
from backend.transformation_approval import LLMTransformationApprovalService
from backend.transformation_diff import LLMTransformationDiffService
from backend.transformation_execution import LLMTransformationExecutionService
from backend.transformation_gate import FAILED as GATE_FAILED
from backend.transformation_gate import LLMTransformationGateService
from backend.transformation_regression import LLMTransformationRegressionService, MissingBaselineError
from backend.transformation_release import LLMTransformationReleaseService
from backend.transformation_rollback import LLMTransformationRollbackService
from backend.transformation_validation import LLMTransformationValidationService
from backend.transformation_verification import LLMTransformationVerificationService

from .models import APPLIED, READY_FOR_RELEASE, REJECTED, RELEASED, ROLLED_BACK, LLMTransformationDecision


class MissingReviewerError(ValueError):
    """Raised when transform() is called without a non-empty 'reviewer' in the request."""


class NotReadyForReleaseError(ValueError):
    """Raised when release() is called for an execution whose decision isn't READY_FOR_RELEASE."""


class UnknownDecisionError(KeyError):
    """Raised when decision()/release() is called for an execution_id with no recorded decision."""


class LLMCodeTransformationOrchestrationService:
    """Unifies Commits #1-#12 into one safe transform -> review -> release pipeline.

    transform() runs plan -> validate -> diff -> approval -> apply -- the
    same Commit #1-#5 chain, called exactly as their own services expose
    it, with 'reviewer' (and an optional 'approved'/'reason' pair for an
    explicit rejection) carried on the same request dict already used for
    planning. review() then runs Commit #6 verification, Commit #7
    regression analysis, and Commit #11's four release gates in order,
    stopping and automatically rolling back (via Commit #9) at the first
    one that fails, so a failed transformation never lingers half-applied.
    release() only ever calls Commit #12's prepare()/release() once
    review() has already recorded READY_FOR_RELEASE. Nothing here
    reimplements a single check any earlier commit already performs, and
    nothing here touches the compiler -- every step is a direct call into
    the service that already owns it. Exactly one LLMTransformationDecision
    is kept per execution_id, replaced (never appended) at each stage, so
    decision(execution_id) is always the one deterministic, current verdict.
    """

    def __init__(
        self,
        transformation_service: LLMCodeTransformationService,
        validation_service: LLMTransformationValidationService,
        diff_service: LLMTransformationDiffService,
        approval_service: LLMTransformationApprovalService,
        execution_service: LLMTransformationExecutionService,
        verification_service: LLMTransformationVerificationService,
        regression_service: LLMTransformationRegressionService,
        gate_service: LLMTransformationGateService,
        release_service: LLMTransformationReleaseService,
        rollback_service: LLMTransformationRollbackService,
    ):
        self._transformation_service = transformation_service
        self._validation_service = validation_service
        self._diff_service = diff_service
        self._approval_service = approval_service
        self._execution_service = execution_service
        self._verification_service = verification_service
        self._regression_service = regression_service
        self._gate_service = gate_service
        self._release_service = release_service
        self._rollback_service = rollback_service
        self._decisions = {}
        self._decision_counter = 0

    def _store_decision(
        self, execution_id, status: str, reason: str, release_id: str = None
    ) -> LLMTransformationDecision:
        self._decision_counter += 1
        key = execution_id if execution_id is not None else f"rejected-{self._decision_counter}"
        decision = LLMTransformationDecision(
            decision_id=f"decision-{key}-{self._decision_counter}",
            execution_id=execution_id,
            status=status,
            release_id=release_id,
            reason=reason,
            created_at=datetime.now(timezone.utc),
        )
        if execution_id is not None:
            self._decisions[execution_id] = decision
        return decision

    def transform(self, notebook_id: str, request: dict) -> LLMTransformationDecision:
        reviewer = request.get("reviewer")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise MissingReviewerError("request must include a non-empty 'reviewer'")

        plan = self._transformation_service.plan(notebook_id, request)
        self._validation_service.validate(plan.plan_id)
        diff = self._diff_service.generate(plan.plan_id)

        if not request.get("approved", True):
            reason = request.get("reason") or "rejected during orchestrated transform"
            self._approval_service.reject(diff.diff_id, reviewer, reason)
            return self._store_decision(None, REJECTED, reason)

        self._approval_service.approve(diff.diff_id, reviewer)
        execution = self._execution_service.apply(diff.diff_id)

        return self._store_decision(execution.execution_id, APPLIED, "transformation applied; pending review")

    def _rolled_back(self, execution_id: str, reason: str) -> LLMTransformationDecision:
        self._rollback_service.rollback(execution_id, reason)
        return self._store_decision(execution_id, ROLLED_BACK, reason)

    def review(self, execution_id: str) -> LLMTransformationDecision:
        self._verification_service.verify(execution_id)
        if self._verification_service.blocking(execution_id):
            return self._rolled_back(execution_id, "verification failed")

        try:
            self._regression_service.analyze(execution_id)
        except MissingBaselineError:
            pass
        else:
            if self._regression_service.critical(execution_id):
                return self._rolled_back(execution_id, "regression detected")

        gates = self._gate_service.evaluate(execution_id)
        if not self._gate_service.passed(execution_id):
            failing = sorted({gate.gate_type for gate in gates if gate.status == GATE_FAILED})
            return self._rolled_back(execution_id, f"gates failed: {', '.join(failing)}")

        return self._store_decision(execution_id, READY_FOR_RELEASE, "all checks passed")

    def _get(self, execution_id: str) -> LLMTransformationDecision:
        try:
            return self._decisions[execution_id]
        except KeyError:
            raise UnknownDecisionError(execution_id)

    def release(self, execution_id: str) -> LLMTransformationDecision:
        decision = self._get(execution_id)
        if decision.status != READY_FOR_RELEASE:
            raise NotReadyForReleaseError(
                f"execution {execution_id!r} is not ready for release (status={decision.status!r})"
            )

        prepared = self._release_service.prepare(execution_id)
        released = self._release_service.release(prepared.release_id)

        return self._store_decision(execution_id, RELEASED, "release created", release_id=released.release_id)

    def rollback(self, execution_id: str) -> LLMTransformationDecision:
        return self._rolled_back(execution_id, "manually rolled back")

    def decision(self, execution_id: str) -> LLMTransformationDecision:
        return self._get(execution_id)
