from .archive_recovery import LLMAgentTaskEventArchiveRecoveryService
from .consistency import LLMAgentTaskEventConsistencyService
from .models import (
    RECOVERY_STAGE_CONSISTENCY,
    RECOVERY_STAGE_PLAN,
    RECOVERY_STAGE_PROJECTION,
    RECOVERY_STAGE_RECOVERY,
    RECOVERY_STAGE_VERIFICATION,
    AgentTaskEventRecoveryOrchestrationResult,
)
from .projection_reconciliation import LLMAgentTaskEventProjectionReconciliationService


class InvalidAgentTaskEventRecoveryOrchestrationError(ValueError):
    """Raised when recover_task_history() is given invalid arguments."""


class LLMAgentTaskEventRecoveryOrchestrationService:
    """Coordinates one real, ordered workflow across four earlier
    commits -- never a new orchestration framework (Rule): every step is
    exactly one call into an existing service (Commit #12's own
    LLMAgentTaskEventArchiveRecoveryService, Commit #5's own
    LLMAgentTaskEventConsistencyService, Commit #8's own
    LLMAgentTaskEventProjectionReconciliationService), sequenced and
    short-circuited by this class, never re-implemented.

    Workflow (Rule: "Preserve stage ordering" -- always attempted in this
    exact order, stopping at the first stage that does not pass):
      1. plan_restore() -- Commit #12's own read-only proposal.
      2. Stop if plan.conflicts is non-empty (RECOVERY_STAGE_PLAN):
         an unrecoverable identity conflict blocks the whole recovery,
         never silently skipped or auto-resolved.
      3+4. recover(plan) -- Commit #12's own recover() already performs
         both "restore missing events" (step 3) and "verify the recovered
         data" (step 4) in one call, since it embeds Commit #11's own
         verify() result directly (Rule: "Do not duplicate logic from
         Commit #11 or #12" -- calling verify() again here would be
         exactly that duplication). recovery_result.unresolved_conflicts
         stops the workflow at RECOVERY_STAGE_RECOVERY (a conflict Commit
         #12's own fresh re-check found that plan_restore() itself did not
         -- see Commit #12's own docstring for why that re-check exists);
         a recovery_result.verification that is not valid stops it at
         RECOVERY_STAGE_VERIFICATION.
      5. validate() -- Commit #5's own consistency check, run against
         task_id's current event stream (post-recovery). A non-consistent
         result stops the workflow at RECOVERY_STAGE_CONSISTENCY.
      6. reconcile() -- Commit #8's own projection reconciliation
         (composing Commit #7's projection, which itself composes Commit
         #3's timeline and Commit #6's replay -- Rule: "Do not duplicate
         logic from Commit #6 or #7" is satisfied by never touching either
         directly). reconcile() itself has no intrinsic "invalid" result
         (it always settles the projection to whatever project() computes);
         the only realistic failure here is an exception from a
         misconfigured or broken collaborator, caught like every other
         stage below.

    Fail-safe by construction (Rule: "a failed stage must not pretend
    later stages succeeded"): every *_result field on the returned
    AgentTaskEventRecoveryOrchestrationResult is None until its own stage
    actually runs and passes -- a stage that stops the workflow leaves
    every later field None, never a placeholder or partially-computed
    value. Each stage's own call is wrapped individually: an unexpected
    exception from a collaborator is caught and reported as that same
    stage's own failure (an orchestration boundary is exactly where broad
    containment is appropriate -- Rule: "Use existing ... error-handling
    conventions where available" is honored by letting each collaborator's
    own specific validation still raise for this service's *own* argument
    checks below, while a downstream collaborator's failure is turned into
    a structured result instead of an uncaught exception, since the whole
    point of a multi-stage result object is to describe exactly where
    things stopped).

    Idempotent by composition, not by any bookkeeping of its own (Rule:
    "Make repeated execution idempotent"): every one of the four composed
    services is already independently idempotent (Commit #12's own
    recover(), Commit #8's own reconcile()), so running the same workflow
    twice in a row with nothing changed in between naturally repeats the
    same outcome.

    Never touches backend.agent_task_lifecycle at all directly (Rule:
    "Keep authoritative task state untouched") -- only through whatever
    consistency_service was constructed with, and only ever via that
    service's own read-only get()/validate().
    """

    def __init__(
        self,
        consistency_service: LLMAgentTaskEventConsistencyService,
        recovery_service: LLMAgentTaskEventArchiveRecoveryService = None,
        projection_reconciliation_service: LLMAgentTaskEventProjectionReconciliationService = None,
    ):
        """
        Args:
            consistency_service: The exact Commit #5
                LLMAgentTaskEventConsistencyService instance to run stage
                5 through -- required, never defaulted (that service's
                own constructor requires a lifecycle_service with no
                usable zero-argument default, so none is invented here
                either).
            recovery_service: Defaults to a fresh
                LLMAgentTaskEventArchiveRecoveryService.
            projection_reconciliation_service: Defaults to a fresh
                LLMAgentTaskEventProjectionReconciliationService.

        The caller is responsible for wiring all three (and
        consistency_service's own lifecycle_service) to the same
        underlying event/task stores -- the same "no auto-wiring across
        services" discipline every composed service in this series
        already requires.
        """
        self._consistency_service = consistency_service
        self._recovery_service = (
            recovery_service if recovery_service is not None else LLMAgentTaskEventArchiveRecoveryService()
        )
        self._projection_reconciliation_service = (
            projection_reconciliation_service
            if projection_reconciliation_service is not None
            else LLMAgentTaskEventProjectionReconciliationService()
        )

    def recover_task_history(
        self, task_id: str, event_ids: list = None
    ) -> AgentTaskEventRecoveryOrchestrationResult:
        """Run the full recover -> verify -> validate -> reconcile
        workflow for task_id, stopping at the first stage that does not
        pass.

        Raises:
            InvalidAgentTaskEventRecoveryOrchestrationError: If task_id is
                not a non-empty string, or event_ids is given and is not
                a list or tuple
        """
        self._require_text(task_id)
        if event_ids is not None and not isinstance(event_ids, (list, tuple)):
            raise InvalidAgentTaskEventRecoveryOrchestrationError("event_ids must be a list or tuple when given")

        try:
            plan = self._recovery_service.plan_restore(task_id, event_ids=event_ids)
        except Exception:
            return self._stopped(task_id, RECOVERY_STAGE_PLAN)

        if plan.conflicts:
            return self._stopped(task_id, RECOVERY_STAGE_PLAN)

        try:
            recovery_result = self._recovery_service.recover(plan)
        except Exception:
            return self._stopped(task_id, RECOVERY_STAGE_RECOVERY)

        if recovery_result.unresolved_conflicts:
            return self._stopped(task_id, RECOVERY_STAGE_RECOVERY, recovery_result=recovery_result)

        verification_result = recovery_result.verification
        if not verification_result.is_valid:
            return self._stopped(
                task_id,
                RECOVERY_STAGE_VERIFICATION,
                recovery_result=recovery_result,
                verification_result=verification_result,
            )

        try:
            consistency_result = self._consistency_service.validate(task_id)
        except Exception:
            return self._stopped(
                task_id,
                RECOVERY_STAGE_CONSISTENCY,
                recovery_result=recovery_result,
                verification_result=verification_result,
            )

        if not consistency_result.is_consistent:
            return self._stopped(
                task_id,
                RECOVERY_STAGE_CONSISTENCY,
                recovery_result=recovery_result,
                verification_result=verification_result,
                consistency_result=consistency_result,
            )

        try:
            projection_result = self._projection_reconciliation_service.reconcile(task_id)
        except Exception:
            return self._stopped(
                task_id,
                RECOVERY_STAGE_PROJECTION,
                recovery_result=recovery_result,
                verification_result=verification_result,
                consistency_result=consistency_result,
            )

        return AgentTaskEventRecoveryOrchestrationResult(
            task_id=task_id,
            recovery_result=recovery_result,
            verification_result=verification_result,
            consistency_result=consistency_result,
            projection_result=projection_result,
            success=True,
            failure_stage=None,
        )

    @staticmethod
    def _stopped(
        task_id: str,
        failure_stage: str,
        recovery_result=None,
        verification_result=None,
        consistency_result=None,
    ) -> AgentTaskEventRecoveryOrchestrationResult:
        return AgentTaskEventRecoveryOrchestrationResult(
            task_id=task_id,
            recovery_result=recovery_result,
            verification_result=verification_result,
            consistency_result=consistency_result,
            projection_result=None,
            success=False,
            failure_stage=failure_stage,
        )

    @staticmethod
    def _require_text(task_id) -> None:
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskEventRecoveryOrchestrationError(
                "task_id is required and must be a non-empty string"
            )
