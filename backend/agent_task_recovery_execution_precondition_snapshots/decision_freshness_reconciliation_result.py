from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional

from .models import (
    RECONCILIATION_COMPLETED,
    RECONCILIATION_UNRESOLVED,
    AgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRecord,
)


class InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultError(ValueError):
    """Raised when record()/get()/latest()/history() is given invalid
    arguments, or the reconciliation result belongs to another task."""


class AgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRawStore(ABC):
    """Raw persistence for reconciliation result records -- the same
    dual-index (result_id, task_id), append-only shape as the decision
    raw store. There is no update()/delete()."""

    @abstractmethod
    def save(
        self, record: AgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRecord
    ) -> AgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRecord:
        ...

    @abstractmethod
    def get(self, result_id: str) -> Optional[AgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRecord]:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRawStore(
    AgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRawStore
):
    """Stores reconciliation result records in memory, for development
    and testing. save() never replaces an existing result_id."""

    def __init__(self):
        self._by_id: dict = {}
        self._by_task: dict = {}

    def save(
        self, record: AgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRecord
    ) -> AgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRecord:
        if record.result_id in self._by_id:
            raise ValueError(f"reconciliation result {record.result_id!r} already exists")
        stored = deepcopy(record)
        self._by_id[record.result_id] = stored
        self._by_task.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def get(self, result_id: str) -> Optional[AgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRecord]:
        record = self._by_id.get(result_id)
        return deepcopy(record) if record is not None else None

    def list_for_task(self, task_id: str) -> list:
        return [deepcopy(entry) for entry in self._by_task.get(task_id, [])]


class LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultService:
    """Persists the outcome of each freshness-chain reconciliation (Commit
    #9) so later runs can tell a completed reconciliation from one that
    still has unresolved conflicts -- a dedicated, append-only store for
    exactly this record type, not a generic result store. The
    reconciliation service stays the source of truth: record() only copies
    an already-computed result's fields verbatim and never reconciles,
    validates, or touches a decision or pointer itself.

    Idempotent for the same reconciliation operation: recording the same
    result twice (same reconciled_at and outcome) returns the existing
    record; prior results are never overwritten. get()/latest()/history()
    are pure reads.
    """

    def __init__(self, store: AgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRawStore = None):
        self._store = (
            store if store is not None
            else InMemoryAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRawStore()
        )

    def record(
        self, task_id: str, reconciliation_result
    ) -> AgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRecord:
        """Persist reconciliation_result for task_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultError:
                If task_id is not a non-empty string, reconciliation_result
                is missing or belongs to another task, or the store failed
        """
        self._require_text(task_id, "task_id")
        if reconciliation_result is None or reconciliation_result.task_id != task_id:
            raise InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultError(
                "reconciliation_result does not belong to the task_id given"
            )

        conflicts = tuple(reconciliation_result.conflicts)
        unresolved = tuple(reconciliation_result.unresolved)
        chain_valid = reconciliation_result.final_chain_valid
        record = AgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRecord(
            task_id=task_id,
            status=(
                RECONCILIATION_COMPLETED if chain_valid and not conflicts and not unresolved
                else RECONCILIATION_UNRESOLVED
            ),
            previous_current_decision_id=reconciliation_result.previous_current_decision_id,
            authoritative_decision_id=reconciliation_result.authoritative_latest_decision_id,
            current_decision_id=reconciliation_result.current_decision_id,
            changed=bool(reconciliation_result.changes), changes=tuple(reconciliation_result.changes),
            conflicts=conflicts, unresolved=unresolved, chain_valid=chain_valid,
            reconciled_at=reconciliation_result.reconciled_at, recorded_at=datetime.now(timezone.utc),
        )
        signature = self._signature(record)
        for existing in self._store.list_for_task(task_id):
            if self._signature(existing) == signature:
                return existing
        try:
            return self._store.save(record)
        except Exception as error:
            raise InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultError(
                f"failed to persist reconciliation result {record.result_id!r}: {error}"
            ) from error

    def get(
        self, task_id: str, result_id: str
    ) -> Optional[AgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRecord]:
        """task_id's exact result_id, or None if it does not exist for
        that task."""
        self._require_text(task_id, "task_id")
        self._require_text(result_id, "result_id")
        record = self._store.get(result_id)
        return record if record is not None and record.task_id == task_id else None

    def latest(self, task_id: str) -> Optional[AgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRecord]:
        """The most recently recorded result for task_id, or None."""
        history = self.history(task_id)
        return history[-1] if history else None

    def history(self, task_id: str) -> list:
        """Every result recorded for task_id, oldest to newest."""
        self._require_text(task_id, "task_id")
        return self._store.list_for_task(task_id)

    @staticmethod
    def _signature(record):
        return (
            record.previous_current_decision_id, record.authoritative_decision_id, record.current_decision_id,
            record.changes, record.conflicts, record.unresolved, record.chain_valid, record.reconciled_at,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultError(
                f"{field_name} is required and must be a non-empty string"
            )
