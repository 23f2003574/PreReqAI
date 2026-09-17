from datetime import datetime, timezone

from .models import NO_OP, REPLACED, AgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryOrchestrationResult
from .trust_change import LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService
from .trust_invalidation import LLMAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationService
from .trust_recovery_audit import LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditService
from .trust_recovery_reconciliation import LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService
from .trust_revalidation import LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationService


class InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryOrchestrationError(ValueError):
    """Raised when recover() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryOrchestrationService:
    """Closes the dependency-snapshot trust lifecycle: detect (Commit #8)
    -> invalidate (Commit #9) -> revalidate (Commit #10) -> audit (Commit
    #11) -> reconcile (Commit #12) -- never a second workflow engine
    (Rule: "Do not introduce generic orchestration infrastructure";
    "Delegate all actual logic to existing services"): recover() is a
    fixed 5-step pipeline calling exactly one already-existing method per
    step, in order, and nothing here re-derives trust, integrity,
    signature, version, or reconciliation logic itself -- matching this
    repository's own recurring "governance orchestrator ties it all
    together" pattern already established at the end of every other
    13-commit series.

    Fail-closed on replacement failure (Rule): reconciliation (step 5) is
    only ever attempted when Commit #10's own revalidate() reports
    REPLACED (a genuinely trusted new snapshot) -- REVALIDATION_FAILED/
    REVALIDATION_MISSING skip reconciliation entirely, leaving
    `reconciliation=None`.

    Never revives the invalid snapshot, never approves/authorizes/
    dispatches/executes recovery (Rule): every one of those guarantees
    already holds in Commit #9/#10/#12 individually; this class adds no
    new write path of its own, so composing them changes nothing about
    those guarantees.

    Idempotent purely by composition (Rule): every one of Commit #8's
    check()/#9's invalidate()/#10's revalidate()/#11's record()/#12's
    reconcile() is already idempotent on its own terms -- no new
    idempotency bookkeeping is added or needed at this layer.

    Handles partial failures explicitly (Rule): step 5 (reconciliation)
    is wrapped in a broad `except Exception` -- an unexpected collaborator
    failure there is captured as `partial_failure`, never left to crash
    the whole recover() call or silently swallowed.
    """

    def __init__(
        self,
        trust_change_service: LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService = None,
        trust_invalidation_service: LLMAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationService = None,
        trust_revalidation_service: LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationService = None,
        audit_service: LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditService = None,
        reconciliation_service: LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService = None,
    ):
        self._trust_change_service = (
            trust_change_service
            if trust_change_service is not None
            else LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService()
        )
        self._trust_invalidation_service = (
            trust_invalidation_service
            if trust_invalidation_service is not None
            else LLMAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationService()
        )
        self._trust_revalidation_service = (
            trust_revalidation_service
            if trust_revalidation_service is not None
            else LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationService()
        )
        self._audit_service = (
            audit_service if audit_service is not None else LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditService()
        )
        self._reconciliation_service = (
            reconciliation_service
            if reconciliation_service is not None
            else LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService()
        )

    def recover(self, task_id: str, snapshot_id: str) -> AgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryOrchestrationResult:
        """Run the full detect -> invalidate -> revalidate -> audit ->
        reconcile pipeline for task_id's exact snapshot_id.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryOrchestrationError:
                If task_id or snapshot_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")
        now = self._now()

        change = self._trust_change_service.check(task_id, snapshot_id)
        if change.current_trust.trusted:
            return AgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryOrchestrationResult(
                task_id=task_id, old_snapshot_id=snapshot_id, new_snapshot_id=snapshot_id, trusted=True,
                action=NO_OP, change=change, invalidation=None, revalidation=None, audit_record=None,
                reconciliation=None, partial_failure=None, recovered_at=now,
            )

        invalidation = self._trust_invalidation_service.invalidate(task_id, snapshot_id)
        revalidation = self._trust_revalidation_service.revalidate(task_id, snapshot_id)
        audit_record = self._audit_service.record(task_id, snapshot_id, revalidation)

        reconciliation = None
        partial_failure = None
        if revalidation.action == REPLACED and revalidation.new_snapshot_id is not None:
            try:
                reconciliation = self._reconciliation_service.reconcile(task_id, snapshot_id, revalidation.new_snapshot_id)
            except Exception as error:
                partial_failure = f"reconciliation failed unexpectedly: {error}"

        trusted = revalidation.new_trust.trusted if revalidation.new_trust is not None else False

        return AgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryOrchestrationResult(
            task_id=task_id, old_snapshot_id=snapshot_id, new_snapshot_id=revalidation.new_snapshot_id,
            trusted=trusted, action=revalidation.action, change=change, invalidation=invalidation,
            revalidation=revalidation, audit_record=audit_record, reconciliation=reconciliation,
            partial_failure=partial_failure, recovered_at=now,
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryOrchestrationError(
                f"{field_name} is required and must be a non-empty string"
            )
