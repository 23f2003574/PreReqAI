from .decision_freshness_audit import LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService
from .decision_freshness_chain_repair import InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore
from .decision_freshness_chain_validation import LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .decision_supersession import (
    InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionService,
)
from .models import (
    INTEGRITY_VALID,
    SUPERSESSION_INVALID,
    SUPERSESSION_VALID,
    AgentTaskRecoveryExecutionDecisionSupersessionValidationResult,
)


class InvalidAgentTaskRecoveryExecutionDecisionSupersessionValidationError(ValueError):
    """Raised when validate() is given an invalid task_id."""


class LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService:
    """Validates the explicit supersession lineage recorded by
    LLMAgentTaskRecoveryExecutionDecisionSupersessionService before it is
    trusted as authoritative -- read-only and never repairing: it only
    reads the supersession records, the decision store, the freshness
    audit trail and the chain index, and compares them.

    Reuses the existing services rather than re-deriving them: the
    authoritative current decision comes from the supersession service's
    own get_current(), agreement with freshness revalidation from Commit
    #7's chain validation, and (optionally) per-decision soundness from
    Commit #1's integrity check. Fails closed: any ambiguity leaves
    terminal_decision_id None.
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        supersession_store=None,
        freshness_audit_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService = None,
        chain_index_store=None,
        supersession_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionService = None,
        chain_validation_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService = None,
        integrity_service=None,
    ):
        """Pass the same decision_store/supersession_store/
        freshness_audit_service/chain_index_store the supersession service
        writes through; the defaults are wired to one another."""
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        self._supersession_store = (
            supersession_store if supersession_store is not None
            else InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore()
        )
        self._audit_service = (
            freshness_audit_service if freshness_audit_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()
        )
        self._index_store = (
            chain_index_store if chain_index_store is not None
            else InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        )
        self._supersession_service = (
            supersession_service if supersession_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionSupersessionService(
                decision_store=self._decision_store, store=self._supersession_store,
                freshness_audit_service=self._audit_service, chain_index_store=self._index_store,
            )
        )
        self._chain_validation_service = (
            chain_validation_service if chain_validation_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService(
                decision_store=self._decision_store, freshness_audit_service=self._audit_service,
                chain_index_store=self._index_store,
            )
        )
        self._integrity_service = integrity_service

    def validate(self, task_id: str) -> AgentTaskRecoveryExecutionDecisionSupersessionValidationResult:
        """Validate task_id's supersession lineage.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionSupersessionValidationError:
                If task_id is not a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionValidationError(
                "task_id is required and must be a non-empty string"
            )

        decisions = self._decision_store.history(task_id)
        records = self._supersession_store.list_for_task(task_id)
        issues = []
        if not decisions:
            issues.append("no decisions are recorded for this task; the lineage cannot be established")
            for record in records:
                issues.append(
                    f"supersession {record.supersession_id} links {record.previous_decision_id} -> "
                    f"{record.replacement_decision_id}, but neither decision is recorded for this task"
                )
            return self._result(task_id, issues, ())

        successors, predecessors, seen_pairs = {}, {}, set()
        for record in records:
            label = f"supersession {record.previous_decision_id} -> {record.replacement_decision_id}"
            if record.task_id != task_id:
                issues.append(f"{label} is recorded for task {record.task_id!r}, not {task_id!r}")
            if not isinstance(record.reason, str) or not record.reason.strip():
                issues.append(f"{label} has no valid supersession reason")
            previous = self._decision_store.get(record.previous_decision_id)
            replacement = self._decision_store.get(record.replacement_decision_id)
            for role, decision_id, decision, recorded_verdict in (
                ("previous", record.previous_decision_id, previous, record.previous_decision),
                ("replacement", record.replacement_decision_id, replacement, record.replacement_decision),
            ):
                if decision is None:
                    issues.append(f"{label}: {role} decision {decision_id} does not exist")
                    continue
                if decision.task_id != task_id:
                    issues.append(
                        f"{label}: {role} decision {decision_id} belongs to task {decision.task_id!r}, not {task_id!r}"
                    )
                if decision.decision != recorded_verdict:
                    issues.append(
                        f"{label}: recorded {role} verdict {recorded_verdict!r} disagrees with the persisted "
                        f"decision's {decision.decision!r}"
                    )
            if previous is not None and replacement is not None and replacement.created_at <= previous.created_at:
                issues.append(f"{label}: the replacement is not newer than the decision it supersedes")

            pair = (record.previous_decision_id, record.replacement_decision_id)
            if pair in seen_pairs:
                issues.append(f"{label} is recorded more than once")
                continue
            seen_pairs.add(pair)
            if pair[0] in successors:
                issues.append(
                    f"decision {pair[0]} has conflicting successors {successors[pair[0]]} and {pair[1]}"
                )
                continue
            if pair[1] in predecessors:
                issues.append(
                    f"decision {pair[1]} supersedes both {predecessors[pair[1]]} and {pair[0]}"
                )
                continue
            successors[pair[0]] = pair[1]
            predecessors[pair[1]] = pair[0]

        for audit in self._audit_service.list(task_id):
            old, new = audit.decision_id, audit.replacement_decision_id
            if new is not None and old in successors and successors[old] != new:
                issues.append(
                    f"supersession {old} -> {successors[old]} disagrees with freshness revalidation "
                    f"{old} -> {new} (audit {audit.audit_id})"
                )

        chain = [decisions[0].decision_id]
        while chain[-1] in successors:
            nxt = successors[chain[-1]]
            if nxt in chain:
                issues.append(f"supersession lineage is cyclic: {' -> '.join(chain + [nxt])}")
                break
            chain.append(nxt)
        terminal = chain[-1]

        current = self._supersession_service.get_current(task_id)
        if current is None:
            issues.append("the authoritative current decision is ambiguous (lineage does not reach the newest decision)")
        elif current != terminal:
            issues.append(
                f"the lineage terminal {terminal} does not match the authoritative current decision {current}"
            )

        freshness = self._chain_validation_service.validate(task_id)
        if not freshness.valid:
            issues.extend(f"freshness chain: {issue}" for issue in freshness.issues)
        elif freshness.latest_decision_id != terminal:
            issues.append(
                f"the freshness chain ends at {freshness.latest_decision_id}, not the lineage terminal {terminal}"
            )
        index = self._index_store.get(task_id)
        if index is not None and index.current_decision_id not in (None, terminal):
            issues.append(
                f"the reconciled current pointer {index.current_decision_id} disagrees with the lineage terminal {terminal}"
            )

        if self._integrity_service is not None:
            for decision_id in chain:
                integrity = self._integrity_service.check(task_id, decision_id)
                if integrity.status != INTEGRITY_VALID:
                    issues.append(f"decision {decision_id} failed its integrity check: {'; '.join(integrity.issues)}")

        return self._result(task_id, issues, tuple(chain))

    @staticmethod
    def _result(task_id, issues, chain):
        status = SUPERSESSION_INVALID if issues else SUPERSESSION_VALID
        return AgentTaskRecoveryExecutionDecisionSupersessionValidationResult(
            task_id=task_id, status=status, issues=tuple(issues), chain=chain,
            terminal_decision_id=chain[-1] if status == SUPERSESSION_VALID else None,
        )
