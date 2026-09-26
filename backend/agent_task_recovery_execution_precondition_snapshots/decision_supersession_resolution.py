from .decision_freshness_audit import LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService
from .decision_freshness_chain_repair import InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .decision_supersession import InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore
from .decision_supersession_validation import LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService
from .models import (
    RESOLUTION_CONFLICT,
    RESOLUTION_REJECTED,
    RESOLUTION_RESOLVED,
    AgentTaskRecoveryExecutionDecisionSupersessionResolutionResult,
)


class InvalidAgentTaskRecoveryExecutionDecisionSupersessionResolutionError(ValueError):
    """Raised when resolve() is given an invalid task_id."""


class LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService:
    """Resolves the authoritative terminal decision from the validated
    supersession lineage -- no new history or reconciliation: the lineage
    is validated by LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService
    (which already rejects cycles, conflicting successors, missing records
    and ambiguous chains, and follows only recorded links -- never
    timestamps), and the result is compared with the freshness
    reconciliation's own current pointer (Commit #8/#9 chain index).

    Only the validated terminal decision is ever selected, with its
    persisted verdict copied verbatim -- nothing is modified, so a
    review/block decision is never turned into allow. A pointer that names
    a different decision is reported as a CONFLICT rather than guessed
    between. Read-only, deterministic and idempotent.
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        supersession_store=None,
        freshness_audit_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService = None,
        chain_index_store=None,
        validation_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService = None,
    ):
        """validation_service, if given, should be built with
        check_reconciled_pointer=False so a pointer disagreement surfaces
        here as a CONFLICT rather than as a rejected lineage."""
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        self._index_store = (
            chain_index_store if chain_index_store is not None
            else InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        )
        self._validation_service = (
            validation_service if validation_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService(
                decision_store=self._decision_store,
                supersession_store=(
                    supersession_store if supersession_store is not None
                    else InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore()
                ),
                freshness_audit_service=(
                    freshness_audit_service if freshness_audit_service is not None
                    else LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()
                ),
                chain_index_store=self._index_store, check_reconciled_pointer=False,
            )
        )

    def resolve(self, task_id: str) -> AgentTaskRecoveryExecutionDecisionSupersessionResolutionResult:
        """Resolve task_id's authoritative terminal decision.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionSupersessionResolutionError:
                If task_id is not a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionResolutionError(
                "task_id is required and must be a non-empty string"
            )

        validation = self._validation_service.validate(task_id)
        index = self._index_store.get(task_id)
        pointer = index.current_decision_id if index is not None else None

        if not validation.valid:
            return self._result(task_id, RESOLUTION_REJECTED, None, validation.chain, (), pointer, validation.issues)

        terminal = validation.terminal_decision_id
        superseded = validation.chain[:-1]
        if pointer is not None and pointer != terminal:
            return self._result(
                task_id, RESOLUTION_CONFLICT, None, validation.chain, superseded, pointer,
                (
                    f"the reconciled current pointer {pointer} disagrees with the supersession terminal "
                    f"{terminal}; not guessing between them",
                ),
            )
        return self._result(task_id, RESOLUTION_RESOLVED, terminal, validation.chain, superseded, pointer, ())

    def _result(self, task_id, state, terminal, chain, superseded, pointer, issues):
        decision = self._decision_store.get(terminal) if terminal is not None else None
        return AgentTaskRecoveryExecutionDecisionSupersessionResolutionResult(
            task_id=task_id, resolution_state=state, terminal_decision_id=terminal,
            terminal_decision=decision.decision if decision is not None else None, chain=tuple(chain),
            superseded_decision_ids=tuple(superseded), reconciled_pointer=pointer, issues=tuple(issues),
        )
