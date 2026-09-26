from datetime import datetime, timezone

from .decision_freshness_audit import LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService
from .decision_freshness_chain_repair import (
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
)
from .decision_freshness_chain_validation import LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .decision_transition import LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService
from .models import (
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationResult,
)


class InvalidAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationError(ValueError):
    """Raised when reconcile() is given an invalid task_id."""


class LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService:
    """Reconciles the task's current decision pointer (Commit #8's own
    chain index) with the authoritative latest decision of the validated
    freshness chain (Commit #7) -- never another decision-management
    system: decisions and audit records are only ever read, the only
    write is the index's current pointer, and a pointer move is explained
    through the existing decision-state transition rules
    (LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService).

    The pointer is only ever moved to the validated chain's terminal
    decision, carrying that decision's own verdict verbatim -- an invalid
    chain (which includes a terminal decision last evaluated stale/
    indeterminate) moves nothing, so no invalid or stale decision is ever
    made current, and no review/block decision is ever rewritten as
    allow. A pointer naming an existing decision that is not on the
    validated chain is a conflict (a divergent claim, not a stale one) and
    is reported rather than overwritten. Read-only when the pointer is
    already consistent; idempotent otherwise.
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        freshness_audit_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService = None,
        chain_index_store: AgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore = None,
        chain_validation_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService = None,
        transition_service: LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService = None,
    ):
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        audit_service = (
            freshness_audit_service
            if freshness_audit_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()
        )
        self._index_store = (
            chain_index_store
            if chain_index_store is not None
            else InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        )
        self._validation_service = (
            chain_validation_service
            if chain_validation_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService(
                decision_store=self._decision_store, freshness_audit_service=audit_service,
                chain_index_store=self._index_store,
            )
        )
        self._transition_service = (
            transition_service
            if transition_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService(store=self._decision_store)
        )

    def reconcile(self, task_id: str) -> AgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationResult:
        """Reconcile task_id's current decision pointer with its validated
        freshness chain.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationError:
                If task_id is not a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationError(
                "task_id is required and must be a non-empty string"
            )

        validation = self._validation_service.validate(task_id)
        index = self._index_store.get(task_id)
        previous = index.current_decision_id if index is not None else None
        authoritative = validation.latest_decision_id
        changes, unresolved, transition = [], [], None
        current = previous

        if not validation.valid:
            unresolved.append("the freshness chain is invalid; the current decision pointer was left unchanged")
            unresolved.extend(validation.issues)
        elif previous == authoritative:
            pass
        elif previous is not None and self._decision_store.get(previous) is not None and previous not in validation.chain:
            unresolved.append(
                f"current pointer {previous} names an existing decision that is not on the validated chain "
                f"(which ends at {authoritative}); conflicting pointers were not guessed between"
            )
        else:
            if previous is not None and self._decision_store.get(previous) is not None:
                try:
                    transition = self._transition_service.analyze(task_id, authoritative, previous)
                except ValueError as error:
                    unresolved.append(f"transition {previous} -> {authoritative} could not be analyzed: {error}")
            if not unresolved:
                self._index_store.save(
                    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex(
                        task_id=task_id, links=index.links if index is not None else (),
                        current_decision_id=authoritative, updated_at=datetime.now(timezone.utc),
                    )
                )
                current = authoritative
                if previous is None:
                    changes.append(f"set current decision pointer to {authoritative}")
                elif transition is None:
                    changes.append(
                        f"replaced current decision pointer {previous}, which references a missing decision, "
                        f"with {authoritative}"
                    )
                else:
                    changes.append(
                        f"advanced stale current decision pointer {previous} -> {authoritative} "
                        f"({transition.transition_type})"
                    )

        current_decision = self._decision_store.get(current) if current is not None else None
        final = self._validation_service.validate(task_id) if changes else validation
        return AgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationResult(
            task_id=task_id, previous_current_decision_id=previous,
            authoritative_latest_decision_id=authoritative, current_decision_id=current,
            current_decision_state=current_decision.decision if current_decision is not None else None,
            changes=tuple(changes), transition=transition, unresolved=tuple(unresolved),
            final_chain_valid=final.valid, reconciled_at=datetime.now(timezone.utc),
        )
