from ..context_freshness import FRESH
from ..context_refresh import InvalidRefreshPlanError, NothingToRefreshError, UnknownRefreshPlanError
from ..context_refresh_execution import FAILED as EXECUTION_FAILED
from ..context_refresh_execution import LLMContextRefreshExecution
from ..context_refresh_validation import LLMContextRefreshValidationService
from .models import (
    ACTIVATED,
    NOOP_FRESH,
    PLANNING_FAILED,
    REFRESH_FAILED,
    VALIDATION_FAILED,
    LLMContextRefreshDecision,
)


class ActivationRefusedError(ValueError):
    """Raised when activate() is asked to confirm a failed or invalid execution."""


class LLMContextRefreshOrchestrationService:
    """Unifies Commits #9-#12 into one safe, deterministic refresh workflow.

    Every step is delegated to the commit that already owns it -- this
    service introduces no second refresh or storage framework, only the
    sequencing and the one decision it needs that nothing upstream already
    represents (LLMContextRefreshDecision):

        freshness check   -> Commit #9  (only a STALE/UNKNOWN context is
                                          ever planned or executed)
        plan()             -> Commit #10 (only its own verified,
                                          real-artifact-backed actions are
                                          ever executed)
        execute()           -> Commit #11 (already applies content the
                                          instant it succeeds -- there is no
                                          separate staging store to write to)
        validate()          -> Commit #12 (checked immediately after
                                          execute(), before this workflow
                                          will call anything "activated")
        rollback()          -> Commit #11 (the undo path both refresh() and
                                          activate() rely on)

    Because Commit #11's execute() already writes the refreshed content
    live, "validate before activation" is enforced here by immediately
    rolling back anything validate() finds invalid -- so a caller can never
    observe an unvalidated refresh as the final state. Every refresh() call
    ends in exactly one of NOOP_FRESH / PLANNING_FAILED / REFRESH_FAILED /
    VALIDATION_FAILED (rolled back) / ACTIVATED, and produces no other
    side effect than the one that outcome describes.
    """

    def __init__(self, validation_service: LLMContextRefreshValidationService):
        self.validation_service = validation_service
        self.execution_service = validation_service.execution_service
        self.refresh_service = validation_service.execution_service.refresh_service
        self.freshness_service = validation_service.freshness_service
        self.context_service = validation_service.context_service
        self.provenance_service = validation_service.provenance_service

    def refresh(self, context_id: str) -> LLMContextRefreshDecision:
        """Check freshness, and only if needed, plan, execute, and validate a refresh.

        A validated refresh is left active; anything else is rolled back
        (or, for a plan/execution that never touched anything, simply never
        applied) so the context always ends this call in a known-good state.
        """
        freshness = self.freshness_service.check(context_id)
        if freshness.status == FRESH:
            return self._decision(context_id, NOOP_FRESH, None, None, None, freshness.reason)

        try:
            plan = self.refresh_service.plan(context_id)
        except NothingToRefreshError as error:
            return self._decision(context_id, NOOP_FRESH, None, None, None, str(error))

        if not plan.refresh_actions:
            return self._decision(
                context_id,
                PLANNING_FAILED,
                plan.plan_id,
                None,
                None,
                f"no actionable, real-artifact-backed refresh source: {plan.reason}",
            )

        try:
            execution = self.execution_service.execute(plan.plan_id)
        except (InvalidRefreshPlanError, UnknownRefreshPlanError) as error:
            return self._decision(context_id, PLANNING_FAILED, plan.plan_id, None, None, str(error))

        if execution.status == EXECUTION_FAILED:
            return self._decision(
                context_id,
                REFRESH_FAILED,
                plan.plan_id,
                execution.execution_id,
                None,
                f"execution {execution.execution_id!r} applied no approved action",
            )

        validation = self.validation_service.validate(execution.execution_id)
        if not validation.valid:
            # Never activate a failed/invalid refresh: undo it immediately
            # so the workflow's final state is always something validated.
            self.execution_service.rollback(execution.execution_id)
            blocking_codes = [finding["code"] for finding in validation.findings if finding["blocking"]]
            return self._decision(
                context_id,
                VALIDATION_FAILED,
                plan.plan_id,
                execution.execution_id,
                validation.validation_id,
                f"validation failed and was rolled back: {blocking_codes}",
            )

        return self._decision(
            context_id,
            ACTIVATED,
            plan.plan_id,
            execution.execution_id,
            validation.validation_id,
            f"execution {execution.execution_id!r} validated with no blocking findings",
        )

    def validate(self, execution_id: str):
        """Commit #12's validate(), exposed directly: no second copy of that logic."""
        return self.validation_service.validate(execution_id)

    def activate(self, execution_id: str) -> LLMContextRefreshDecision:
        """Confirm a specific execution as active. Refuses a failed or invalid one."""
        execution = self.execution_service.status(execution_id)
        validation = self.validation_service.validate(execution_id)

        if execution.status == EXECUTION_FAILED or not validation.valid:
            raise ActivationRefusedError(
                f"execution {execution_id!r} cannot be activated: "
                f"status={execution.status!r}, valid={validation.valid}"
            )

        plan = self.refresh_service.get(execution.plan_id)
        return self._decision(
            plan.context_id,
            ACTIVATED,
            execution.plan_id,
            execution.execution_id,
            validation.validation_id,
            f"execution {execution_id!r} validated with no blocking findings",
        )

    def rollback(self, execution_id: str) -> LLMContextRefreshExecution:
        """Commit #11's rollback(), exposed directly: no second copy of that logic."""
        return self.execution_service.rollback(execution_id)

    def status(self, execution_id: str) -> LLMContextRefreshExecution:
        """Commit #11's status(), exposed directly: no second copy of that logic."""
        return self.execution_service.status(execution_id)

    # -- internals ------------------------------------------------------

    def _decision(
        self,
        context_id,
        outcome: str,
        plan_id,
        execution_id,
        validation_id,
        reason: str,
    ) -> LLMContextRefreshDecision:
        return LLMContextRefreshDecision(
            context_id=context_id,
            outcome=outcome,
            reason=reason,
            plan_id=plan_id,
            execution_id=execution_id,
            validation_id=validation_id,
        )
