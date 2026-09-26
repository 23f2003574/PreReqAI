from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional

from .decision_freshness_audit import LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService
from .decision_freshness_chain_validation import LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .models import (
    EXECUTION_DECISION_ALLOW,
    REVALIDATION_REPLACED,
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionDecisionFreshnessChainRepairResult,
)


class InvalidAgentTaskRecoveryExecutionDecisionFreshnessChainRepairError(ValueError):
    """Raised when repair() is given an invalid task_id."""


class AgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore(ABC):
    """Raw storage for the derived, non-authoritative
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex -- one entry per
    task, replaced wholesale on save(). Holds only metadata derivable from
    the decision store and audit trail, never a decision or audit record."""

    @abstractmethod
    def get(self, task_id: str) -> Optional[AgentTaskRecoveryExecutionDecisionFreshnessChainIndex]:
        ...

    @abstractmethod
    def save(
        self, index: AgentTaskRecoveryExecutionDecisionFreshnessChainIndex
    ) -> AgentTaskRecoveryExecutionDecisionFreshnessChainIndex:
        ...


class InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore(
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore
):
    """In-memory chain index storage, for development and testing."""

    def __init__(self):
        self._by_task: dict = {}

    def get(self, task_id: str) -> Optional[AgentTaskRecoveryExecutionDecisionFreshnessChainIndex]:
        index = self._by_task.get(task_id)
        return deepcopy(index) if index is not None else None

    def save(
        self, index: AgentTaskRecoveryExecutionDecisionFreshnessChainIndex
    ) -> AgentTaskRecoveryExecutionDecisionFreshnessChainIndex:
        self._by_task[index.task_id] = deepcopy(index)
        return deepcopy(index)


class LLMAgentTaskRecoveryExecutionDecisionFreshnessChainRepairService:
    """Repairs only mechanically recoverable freshness-chain
    inconsistencies, and only in derived metadata -- never in history
    (Rule: "Never modify historical decision contents"): the decision store
    and the freshness audit trail are only ever read; every write goes to
    the non-authoritative chain index, which Commit #7's own chain
    validation reads as supplementary linkage.

    Repairable:
      * missing linkage -- an audit recorded a REPLACED revalidation of an
        existing decision but lost the replacement id, and exactly one
        existing decision could be that replacement (created after the old
        decision, no later than the audit, not already linked);
      * stale current-pointer/reference metadata -- a derived link naming
        a decision that no longer exists, or a current pointer that no
        longer matches the validated chain terminal;
      * duplicate non-authoritative linkage -- repeated derived links, or
        derived links the audit trail already records itself.

    Never manufactures a decision or audit record, never infers a link
    that would silently turn a REVIEW/BLOCK decision into ALLOW (reported
    unresolved instead), never executes recovery or touches authorization.
    Chain validation runs before and after; the current pointer is set
    only when the final validation passes (fail closed). Idempotent: a
    second repair() of an unchanged task repairs nothing.
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        freshness_audit_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService = None,
        chain_index_store: AgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore = None,
        chain_validation_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService = None,
    ):
        """
        Args:
            chain_validation_service: Defaults to one built from the same
                decision_store/freshness_audit_service/chain_index_store --
                pass one wired to that same chain_index_store, or repairs
                will not be visible to it.
        """
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        self._audit_service = (
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
                decision_store=self._decision_store, freshness_audit_service=self._audit_service,
                chain_index_store=self._index_store,
            )
        )

    def repair(self, task_id: str) -> AgentTaskRecoveryExecutionDecisionFreshnessChainRepairResult:
        """Repair task_id's recoverable chain inconsistencies.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionFreshnessChainRepairError:
                If task_id is not a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionFreshnessChainRepairError(
                "task_id is required and must be a non-empty string"
            )

        initial = self._validation_service.validate(task_id)
        decisions = self._decision_store.history(task_id)
        audits = self._audit_service.list(task_id)
        by_id = {decision.decision_id: decision for decision in decisions}
        index = self._index_store.get(task_id)
        repaired, unresolved = [], []

        audit_links = {
            (audit.decision_id, audit.replacement_decision_id)
            for audit in audits if audit.replacement_decision_id is not None
        }
        links, seen = [], set()
        for old_id, new_id in (index.links if index is not None else ()):
            if (old_id, new_id) in seen:
                repaired.append(f"removed duplicate derived link {old_id} -> {new_id}")
                continue
            seen.add((old_id, new_id))
            if (old_id, new_id) in audit_links:
                repaired.append(f"removed derived link {old_id} -> {new_id}, already recorded by the audit trail")
            elif old_id not in by_id or new_id not in by_id:
                repaired.append(f"removed derived link {old_id} -> {new_id}, which references a missing decision")
            else:
                links.append((old_id, new_id))

        linked_old = {old for old, _ in audit_links} | {old for old, _ in links}
        linked_new = {new for _, new in audit_links} | {new for _, new in links}
        for audit in audits:
            if audit.revalidation_action != REVALIDATION_REPLACED or audit.replacement_decision_id is not None:
                continue
            old = by_id.get(audit.decision_id)
            if old is None:
                unresolved.append(
                    f"audit {audit.audit_id} records a replacement of missing decision {audit.decision_id}; "
                    "nothing to link"
                )
                continue
            if old.decision_id in linked_old:
                continue
            candidates = [
                decision for decision in decisions
                if decision.decision_id != old.decision_id and decision.decision_id not in linked_new
                and old.created_at < decision.created_at <= audit.recorded_at
            ]
            if len(candidates) != 1:
                unresolved.append(
                    f"audit {audit.audit_id} lost the replacement of decision {old.decision_id} and "
                    f"{len(candidates)} existing decisions could be it; link not inferred"
                )
                continue
            successor = candidates[0]
            if old.decision != EXECUTION_DECISION_ALLOW and successor.decision == EXECUTION_DECISION_ALLOW:
                unresolved.append(
                    f"inferring {old.decision_id} -> {successor.decision_id} would silently turn a "
                    f"{old.decision} decision into allow; link not inferred"
                )
                continue
            links.append((old.decision_id, successor.decision_id))
            linked_old.add(old.decision_id)
            linked_new.add(successor.decision_id)
            repaired.append(
                f"linked {old.decision_id} -> {successor.decision_id} from audit {audit.audit_id}"
            )

        old_pointer = index.current_decision_id if index is not None else None
        if index is None or tuple(links) != index.links:
            self._save(task_id, links, old_pointer)
        final = self._validation_service.validate(task_id)
        if final.latest_decision_id != old_pointer:
            self._save(task_id, links, final.latest_decision_id)
            repaired.append(
                f"updated current decision pointer from {old_pointer} to {final.latest_decision_id}"
            )

        for issue in final.issues:
            if issue not in unresolved:
                unresolved.append(issue)

        return AgentTaskRecoveryExecutionDecisionFreshnessChainRepairResult(
            task_id=task_id, repaired=tuple(repaired), unresolved=tuple(unresolved),
            initial_validation=initial, final_validation=final, repaired_at=datetime.now(timezone.utc),
        )

    def _save(self, task_id, links, current_decision_id):
        self._index_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessChainIndex(
                task_id=task_id, links=tuple(links), current_decision_id=current_decision_id,
                updated_at=datetime.now(timezone.utc),
            )
        )
