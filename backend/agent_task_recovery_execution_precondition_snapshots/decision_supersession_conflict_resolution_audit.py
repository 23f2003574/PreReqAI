from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone

from .models import (
    CONFLICT_ACTION_APPLIED,
    CONFLICT_ACTION_DELEGATED,
    AgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditRecord,
)


class InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditError(ValueError):
    """Raised when record() is given invalid arguments or a result for
    another task."""


class AgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditStore(ABC):
    """Raw, append-only persistence for conflict-resolution audit records
    -- the same dual-index (audit_id, task_id) shape as the package's
    other audit stores. There is no update()/delete()."""

    @abstractmethod
    def save(self, record):
        ...

    @abstractmethod
    def get(self, audit_id: str):
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditStore(
    AgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditStore
):
    """Stores conflict-resolution audit records in memory, for development
    and testing."""

    def __init__(self):
        self._by_id: dict = {}
        self._by_task: dict = {}

    def save(self, record):
        stored = deepcopy(record)
        self._by_id[record.audit_id] = stored
        self._by_task.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def get(self, audit_id: str):
        record = self._by_id.get(audit_id)
        return deepcopy(record) if record is not None else None

    def list_for_task(self, task_id: str) -> list:
        return [deepcopy(entry) for entry in self._by_task.get(task_id, [])]


class LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService:
    """Records exactly what a conflict-resolution operation (#8) applied,
    delegated, skipped and failed -- an immutable operational audit kept
    apart from the mutation logic, following the package's existing
    append-only audit conventions (and #11's schema_version convention).
    record() only copies an already-computed resolution result verbatim
    -- exact conflict and decision ids, failure reasons, and the pre/post
    chain validation status -- and never touches a decision.

    Idempotent per operation: recording the same resolution result
    (same operation_id) again returns the existing record.
    """

    def __init__(self, store: AgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditStore = None):
        self._store = (
            store if store is not None
            else InMemoryAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditStore()
        )

    def record(
        self, task_id: str, resolution_result
    ) -> AgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditRecord:
        """Record resolution_result for task_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditError:
                If task_id is not a non-empty string, or resolution_result
                is missing or belongs to another task
        """
        self._require_text(task_id, "task_id")
        if resolution_result is None or resolution_result.task_id != task_id:
            raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditError(
                "resolution_result does not belong to the task_id given"
            )
        for existing in self._store.list_for_task(task_id):
            if existing.operation_id == resolution_result.operation_id:
                return existing

        outcomes = resolution_result.applied + resolution_result.skipped + resolution_result.failed
        conflict_ids = []
        for conflict_id in [o.conflict_id for o in outcomes] + list(resolution_result.still_blocking):
            if conflict_id not in conflict_ids:
                conflict_ids.append(conflict_id)
        pre, post = resolution_result.initial_validation, resolution_result.final_validation
        record = AgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditRecord(
            task_id=task_id, operation_id=resolution_result.operation_id, conflict_ids=tuple(conflict_ids),
            applied=tuple(o for o in resolution_result.applied if o.outcome == CONFLICT_ACTION_APPLIED),
            delegated=tuple(o for o in resolution_result.applied if o.outcome == CONFLICT_ACTION_DELEGATED),
            skipped=tuple(resolution_result.skipped), failed=tuple(resolution_result.failed),
            still_blocking=tuple(resolution_result.still_blocking), plan_valid=resolution_result.plan_valid,
            pre_chain_status=pre.status if pre is not None else None,
            pre_terminal_decision_id=pre.terminal_decision_id if pre is not None else None,
            post_chain_status=post.status if post is not None else None,
            post_terminal_decision_id=post.terminal_decision_id if post is not None else None,
            executed_at=resolution_result.executed_at, recorded_at=datetime.now(timezone.utc),
        )
        return self._store.save(record)

    def get(self, audit_id: str):
        """The exact audit_id's record, or None."""
        self._require_text(audit_id, "audit_id")
        return self._store.get(audit_id)

    def list(self, task_id: str) -> list:
        """Every conflict-resolution audit record for task_id, oldest first."""
        self._require_text(task_id, "task_id")
        return self._store.list_for_task(task_id)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditError(
                f"{field_name} is required and must be a non-empty string"
            )
