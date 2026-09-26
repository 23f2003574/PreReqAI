from datetime import datetime, timezone

from .decision_freshness_audit import LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService
from .decision_freshness_chain_reconciliation import (
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService,
)
from .decision_freshness_chain_repair import InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore
from .decision_freshness_chain_validation import LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService
from .decision_freshness_reconciliation_audit import (
    LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditService,
)
from .decision_freshness_reconciliation_result import (
    LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultService,
)
from .decision_freshness_reconciliation_verification import (
    LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationVerificationService,
)
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .models import (
    LIFECYCLE_COMPLETED,
    LIFECYCLE_FAILED,
    LIFECYCLE_UNRESOLVED,
    RECONCILIATION_COMPLETED,
    AgentTaskRecoveryExecutionDecisionFreshnessReconciliationLifecycleResult,
)


class InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationLifecycleError(ValueError):
    """Raised when reconcile() is given an invalid task_id."""


class LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationLifecycleService:
    """Closes the freshness-reconciliation lifecycle as one maintenance
    operation, composing -- never re-implementing -- Commit #7's chain
    validation, #9's reconciliation, #10's audit, #11's result persistence
    and #12's verification:

      1. validate the chain;
      2. verify the latest persisted reconciliation result, if any;
      3. reconcile only when that result is missing, fails verification,
         is unresolved, or no longer matches the current pointer;
      4. persist the reconciliation result;
      5. record the reconciliation audit;
      6. verify the persisted result again.

    Every business rule lives in those services: decisions are never
    rewritten, review/block is never turned into allow, and an
    authoritative decision is never guessed (#9 fails closed and #12
    verifies it). Idempotent: when the latest persisted result is already
    current and verified, nothing is reconciled, persisted or audited.
    A persistence/audit failure is reported (status FAILED), never
    swallowed. Never executes recovery or modifies authorization.
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        freshness_audit_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService = None,
        chain_index_store=None,
        chain_validation_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService = None,
        reconciliation_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService = None,
        result_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultService = None,
        audit_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditService = None,
        verification_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationVerificationService = None,
    ):
        """Defaults are wired to the SAME decision_store/
        freshness_audit_service/chain_index_store; pass real instances
        sharing those stores when overriding any collaborator."""
        decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        freshness_audit_service = (
            freshness_audit_service if freshness_audit_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()
        )
        self._index_store = (
            chain_index_store if chain_index_store is not None
            else InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        )
        self._validation_service = (
            chain_validation_service if chain_validation_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService(
                decision_store=decision_store, freshness_audit_service=freshness_audit_service,
                chain_index_store=self._index_store,
            )
        )
        self._reconciliation_service = (
            reconciliation_service if reconciliation_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService(
                decision_store=decision_store, freshness_audit_service=freshness_audit_service,
                chain_index_store=self._index_store, chain_validation_service=self._validation_service,
            )
        )
        self._result_service = (
            result_service if result_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultService()
        )
        self._audit_service = (
            audit_service if audit_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditService()
        )
        self._verification_service = (
            verification_service if verification_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationVerificationService(
                result_service=self._result_service, decision_store=decision_store,
                chain_validation_service=self._validation_service,
            )
        )

    def reconcile(self, task_id: str) -> AgentTaskRecoveryExecutionDecisionFreshnessReconciliationLifecycleResult:
        """Run the freshness-reconciliation lifecycle for task_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationLifecycleError:
                If task_id is not a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationLifecycleError(
                "task_id is required and must be a non-empty string"
            )

        validation = self._validation_service.validate(task_id)
        latest = self._result_service.latest(task_id)
        prior_verification = (
            self._verification_service.verify(task_id, latest.result_id) if latest is not None else None
        )
        index = self._index_store.get(task_id)
        pointer = index.current_decision_id if index is not None else None

        if (
            latest is not None and prior_verification.valid and latest.status == RECONCILIATION_COMPLETED
            and validation.valid and pointer == latest.current_decision_id
        ):
            return self._result(
                task_id, LIFECYCLE_COMPLETED, False, pointer, latest.current_decision_id,
                latest.authoritative_decision_id, (), latest.conflicts, latest.unresolved, latest.result_id,
                None, validation.valid, prior_verification, prior_verification, (),
            )

        reconciliation = self._reconciliation_service.reconcile(task_id)
        # A no-op reconciliation that reproduces the latest, still-verified
        # (unresolved) result exactly is already recorded -- appending it
        # again would only duplicate history.
        if (
            latest is not None and prior_verification.valid and not reconciliation.changes
            and (
                reconciliation.current_decision_id, reconciliation.authoritative_latest_decision_id,
                tuple(reconciliation.conflicts), tuple(reconciliation.unresolved),
                reconciliation.final_chain_valid,
            ) == (
                latest.current_decision_id, latest.authoritative_decision_id, latest.conflicts,
                latest.unresolved, latest.chain_valid,
            )
        ):
            return self._result(
                task_id, LIFECYCLE_UNRESOLVED if latest.status != RECONCILIATION_COMPLETED else LIFECYCLE_COMPLETED,
                False, reconciliation.previous_current_decision_id, reconciliation.current_decision_id,
                reconciliation.authoritative_latest_decision_id, (), reconciliation.conflicts,
                reconciliation.unresolved, latest.result_id, None, validation.valid, prior_verification,
                prior_verification, (),
            )

        errors, record, audit = [], None, None
        try:
            record = self._result_service.record(task_id, reconciliation)
        except Exception as error:
            errors.append(f"persisting the reconciliation result failed: {error}")
        try:
            audit = self._audit_service.record(task_id, reconciliation)
        except Exception as error:
            errors.append(f"recording the reconciliation audit failed: {error}")

        final_verification = (
            self._verification_service.verify(task_id, record.result_id) if record is not None else None
        )
        if errors or final_verification is None or not final_verification.valid:
            status = LIFECYCLE_FAILED
        elif record.status == RECONCILIATION_COMPLETED:
            status = LIFECYCLE_COMPLETED
        else:
            status = LIFECYCLE_UNRESOLVED

        return self._result(
            task_id, status, True, reconciliation.previous_current_decision_id,
            reconciliation.current_decision_id, reconciliation.authoritative_latest_decision_id,
            reconciliation.changes, reconciliation.conflicts, reconciliation.unresolved,
            record.result_id if record is not None else None, audit.audit_id if audit is not None else None,
            validation.valid, prior_verification, final_verification, tuple(errors),
        )

    @staticmethod
    def _result(
        task_id, status, performed, previous, current, authoritative, changes, conflicts, unresolved,
        result_id, audit_id, initial_chain_valid, prior_verification, final_verification, errors,
    ):
        return AgentTaskRecoveryExecutionDecisionFreshnessReconciliationLifecycleResult(
            task_id=task_id, status=status, reconciliation_performed=performed,
            previous_current_decision_id=previous, current_decision_id=current,
            authoritative_decision_id=authoritative, changes=tuple(changes), conflicts=tuple(conflicts),
            unresolved=tuple(unresolved), result_id=result_id, audit_id=audit_id,
            initial_chain_valid=initial_chain_valid, prior_verification=prior_verification,
            final_verification=final_verification, errors=errors, completed_at=datetime.now(timezone.utc),
        )
