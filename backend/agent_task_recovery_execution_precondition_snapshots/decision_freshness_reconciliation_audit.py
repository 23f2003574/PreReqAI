from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional

from .models import AgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditRecord


class InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditError(ValueError):
    """Raised when record() is given invalid arguments, or the
    reconciliation result does not belong to the task_id given."""


class AgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditStore(ABC):
    """Raw persistence for reconciliation audit records -- the same
    dual-index (audit_id, task_id), append-only shape as
    AgentTaskRecoveryExecutionDecisionFreshnessAuditStore. There is no
    update()/delete()."""

    @abstractmethod
    def save(
        self, record: AgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditRecord
    ) -> AgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditRecord:
        ...

    @abstractmethod
    def get(self, audit_id: str) -> Optional[AgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditRecord]:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditStore(
    AgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditStore
):
    """Stores reconciliation audit records in memory, for development and
    testing."""

    def __init__(self):
        self._by_id: dict = {}
        self._by_task: dict = {}

    def save(
        self, record: AgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditRecord
    ) -> AgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditRecord:
        stored = deepcopy(record)
        self._by_id[record.audit_id] = stored
        self._by_task.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def get(self, audit_id: str) -> Optional[AgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditRecord]:
        record = self._by_id.get(audit_id)
        return deepcopy(record) if record is not None else None

    def list_for_task(self, task_id: str) -> list:
        entries = self._by_task.get(task_id, [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.recorded_at)]


class LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditService:
    """Records an immutable, append-only trail of every freshness-chain
    reconciliation -- no-op and state-changing alike, so each pointer
    change (and each time the pointer was confirmed or left unresolved)
    stays traceable. Follows Commit #5's freshness audit conventions
    rather than adding another audit framework: record() only accepts an
    already-computed reconciliation result and persists its fields
    verbatim (exact decision IDs, conflicts, unresolved issues); it never
    calls reconcile()/validate() and never touches a decision or pointer.

    Idempotent for the same reconciliation operation: recording the same
    result twice (same reconciled_at and outcome) returns the existing
    record instead of appending a duplicate. A later reconciliation --
    even with an identical outcome -- is a distinct operation and is
    always appended.
    """

    def __init__(self, store: AgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditStore = None):
        self._store = (
            store if store is not None else InMemoryAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditStore()
        )

    def record(
        self, task_id: str, reconciliation_result
    ) -> AgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditRecord:
        """Record reconciliation_result for task_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditError:
                If task_id is not a non-empty string, or
                reconciliation_result is missing or belongs to another task
        """
        self._require_text(task_id, "task_id")
        if reconciliation_result is None or reconciliation_result.task_id != task_id:
            raise InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditError(
                "reconciliation_result does not belong to the task_id given"
            )

        record = AgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditRecord(
            task_id=task_id,
            previous_current_decision_id=reconciliation_result.previous_current_decision_id,
            authoritative_decision_id=reconciliation_result.authoritative_latest_decision_id,
            current_decision_id=reconciliation_result.current_decision_id,
            changed=bool(reconciliation_result.changes), changes=tuple(reconciliation_result.changes),
            conflicts=tuple(reconciliation_result.conflicts), chain_valid=reconciliation_result.final_chain_valid,
            unresolved=tuple(reconciliation_result.unresolved), reconciled_at=reconciliation_result.reconciled_at,
            recorded_at=datetime.now(timezone.utc),
        )
        signature = self._signature(record)
        for existing in self._store.list_for_task(task_id):
            if self._signature(existing) == signature:
                return existing
        return self._store.save(record)

    def get(self, audit_id: str) -> Optional[AgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditRecord]:
        """The exact audit_id's own record, or None if it does not exist."""
        self._require_text(audit_id, "audit_id")
        return self._store.get(audit_id)

    def list(self, task_id: str) -> list:
        """Every reconciliation audit entry for task_id, oldest to newest."""
        self._require_text(task_id, "task_id")
        return self._store.list_for_task(task_id)

    @staticmethod
    def _signature(record):
        return (
            record.previous_current_decision_id, record.authoritative_decision_id, record.current_decision_id,
            record.changes, record.conflicts, record.chain_valid, record.unresolved, record.reconciled_at,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditError(
                f"{field_name} is required and must be a non-empty string"
            )
