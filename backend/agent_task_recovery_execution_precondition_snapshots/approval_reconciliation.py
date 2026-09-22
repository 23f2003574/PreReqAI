from datetime import datetime, timezone

from backend.agent_task_recovery_guardrails import APPROVED, LLMAgentTaskRecoveryPreflightApprovalService

from .models import (
    RECONCILED_PRESERVED,
    RECONCILED_REQUIRES_REVIEW,
    RECONCILED_REVOKED,
    REVALIDATION_REUSED,
    AgentTaskRecoveryExecutionPreconditionApprovalReconciliationResult,
)
from .revalidation import LLMAgentTaskRecoveryExecutionPreconditionRevalidationService
from .service import LLMAgentTaskRecoveryExecutionPreconditionSnapshotService


class InvalidAgentTaskRecoveryExecutionPreconditionApprovalReconciliationError(ValueError):
    """Raised when reconcile() is given invalid arguments, or snapshot_id
    names no recorded Commit #1 snapshot for task_id."""


class LLMAgentTaskRecoveryExecutionPreconditionApprovalReconciliationService:
    """Determines whether an existing backend.agent_task_recovery_guardrails.
    AgentTaskRecoveryPreflightApproval still applies to the CURRENT
    execution-precondition state -- never a second approval system (Rule:
    "Do not create another approval system"): reconcile() calls Commit
    #4's own revalidate() exactly once and backend.
    agent_task_recovery_guardrails.LLMAgentTaskRecoveryPreflightApprovalService.
    get() (a pure read) -- it never calls request()/approve()/reject() or
    any other write path on the approval store, and never calls
    authorize()/revoke() on the authorization store either.

    Never silently carries approval from an outdated execution state
    (Rule: this is the whole point): PRESERVED is reported only when
    Commit #4's own revalidate() found the ORIGINAL snapshot/preflight/
    authorization still current with nothing blocking at all AND that
    exact preflight's own approval is already APPROVED -- any rebuild,
    material drift, changed recommended action, or missing/pending/
    rejected approval instead reports REQUIRES_REVIEW, and an
    authorization Commit #4 could not resolve at all reports REVOKED.

    Never automatically approves a materially changed recovery, and keeps
    old approval history immutable (Rule): this class has no code path
    that ever writes anything -- REQUIRES_REVIEW/REVOKED are read-only
    verdicts about the SITUATION, never a status this class stamps onto
    any stored approval record. Reuses existing approval/authorization
    state transitions (Rule) by reading whatever an operator's own
    approve()/reject()/revoke() call already produced, rather than
    performing a parallel transition of its own.

    Idempotent by composition (Rule): Commit #4's own revalidate() is
    already idempotent, and approval_service.get() is a pure read --
    calling reconcile() twice in a row with nothing else changed always
    returns an identical result.
    """

    def __init__(
        self,
        snapshot_service: LLMAgentTaskRecoveryExecutionPreconditionSnapshotService = None,
        revalidation_service: LLMAgentTaskRecoveryExecutionPreconditionRevalidationService = None,
        approval_service: LLMAgentTaskRecoveryPreflightApprovalService = None,
    ):
        """
        Args:
            snapshot_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionSnapshotService;
                pass the real instance holding the snapshot capture()
                actually produced.
            revalidation_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionRevalidationService;
                pass the real instance wired to the same snapshot/drift/
                authorization stack.
            approval_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightApprovalService; pass the
                real instance holding a task's actual approval records.
        """
        self._snapshot_service = (
            snapshot_service
            if snapshot_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionSnapshotService()
        )
        self._revalidation_service = (
            revalidation_service
            if revalidation_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionRevalidationService()
        )
        self._approval_service = (
            approval_service if approval_service is not None else LLMAgentTaskRecoveryPreflightApprovalService()
        )

    def reconcile(
        self, task_id: str, snapshot_id: str
    ) -> AgentTaskRecoveryExecutionPreconditionApprovalReconciliationResult:
        """Reconcile task_id's existing approval against its exact Commit
        #1 snapshot_id's current execution-precondition state.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionApprovalReconciliationError:
                If task_id/snapshot_id is not a non-empty string, or
                snapshot_id names no recorded snapshot for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")

        old_snapshot = self._snapshot_service.get(task_id, snapshot_id)
        if old_snapshot is None:
            raise InvalidAgentTaskRecoveryExecutionPreconditionApprovalReconciliationError(
                f"no snapshot {snapshot_id!r} is recorded for task_id {task_id!r}"
            )

        revalidation = self._revalidation_service.revalidate(task_id, snapshot_id)
        old_preflight_id = old_snapshot.preflight_id
        old_authorization_id = old_snapshot.authorization_id
        old_approval = self._approval_service.get(task_id, old_preflight_id)

        current_snapshot_id = revalidation.new_snapshot_id
        current_snapshot = self._snapshot_service.get(task_id, current_snapshot_id) if current_snapshot_id else None
        current_preflight_id = current_snapshot.preflight_id if current_snapshot is not None else None
        current_authorization_id = current_snapshot.authorization_id if current_snapshot is not None else None

        current_approval = (
            old_approval if current_preflight_id == old_preflight_id
            else (self._approval_service.get(task_id, current_preflight_id) if current_preflight_id else None)
        )

        if current_snapshot is None:
            state = RECONCILED_REVOKED
            reason = revalidation.reason or "no active authorization exists; approval no longer applies"
        elif revalidation.action == REVALIDATION_REUSED and current_approval is not None and current_approval.status == APPROVED:
            state = RECONCILED_PRESERVED
            reason = "the authorized action and all material execution conditions are unchanged"
        else:
            state = RECONCILED_REQUIRES_REVIEW
            reason = self._require_review_reason(old_snapshot, current_snapshot, current_approval, old_preflight_id, current_preflight_id)

        return AgentTaskRecoveryExecutionPreconditionApprovalReconciliationResult(
            task_id=task_id,
            previous_snapshot_id=snapshot_id,
            current_snapshot_id=current_snapshot_id,
            previous_preflight_id=old_preflight_id,
            current_preflight_id=current_preflight_id,
            previous_authorization_id=old_authorization_id,
            current_authorization_id=current_authorization_id,
            state=state,
            previous_approval=old_approval,
            current_approval=current_approval,
            revalidation=revalidation,
            reason=reason,
            reconciled_at=self._now(),
        )

    @staticmethod
    def _require_review_reason(old_snapshot, current_snapshot, current_approval, old_preflight_id, current_preflight_id) -> str:
        if current_approval is None:
            return "no approval is recorded for the current preflight"
        if current_approval.status != APPROVED:
            return f"the current approval is {current_approval.status!r}, not approved"

        old_plan = old_snapshot.recovery_plan
        new_plan = current_snapshot.recovery_plan
        if (
            old_plan is not None
            and new_plan is not None
            and old_plan.recommended_action != new_plan.recommended_action
        ):
            return (
                f"the recommended recovery action changed from {old_plan.recommended_action!r} to "
                f"{new_plan.recommended_action!r} since approval; the rebuild must still be reviewed"
            )
        if current_preflight_id != old_preflight_id:
            return "recovery was just rebuilt against a different preflight and must still be reviewed"
        return "material drift triggered a rebuild since the original approval; it must still be reviewed"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionPreconditionApprovalReconciliationError(
                f"{field_name} is required and must be a non-empty string"
            )
