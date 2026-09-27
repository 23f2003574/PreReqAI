from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional

from .models import AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultRecord


class InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultError(ValueError):
    """Raised when record()/get()/latest()/history() is given invalid
    arguments, or the lifecycle result belongs to another task."""


class AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultRawStore(ABC):
    """Raw, append-only persistence for impact-invalidation lifecycle result
    records -- the same dual-index (result_id, task_id) shape as the
    reconciliation result store. There is no update()/delete()."""

    @abstractmethod
    def save(self, record):
        ...

    @abstractmethod
    def get(self, result_id: str):
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultRawStore(
    AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultRawStore
):
    """In-memory lifecycle result storage, for development and testing.
    save() never replaces an existing result_id."""

    def __init__(self):
        self._by_id: dict = {}
        self._by_task: dict = {}

    def save(self, record):
        if record.result_id in self._by_id:
            raise ValueError(f"lifecycle result {record.result_id!r} already exists")
        stored = deepcopy(record)
        self._by_id[record.result_id] = stored
        self._by_task.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def get(self, result_id: str):
        record = self._by_id.get(result_id)
        return deepcopy(record) if record is not None else None

    def list_for_task(self, task_id: str) -> list:
        return [deepcopy(entry) for entry in self._by_task.get(task_id, [])]


class LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultService:
    """Persists the consolidated outcome of each impact-invalidation
    lifecycle run (#8) so it can be inspected and verified later -- a
    dedicated append-only store for this one record type, following the
    existing result persistence conventions (schema_version,
    get/latest/history), not a generic workflow-result framework.

    record() copies the lifecycle result verbatim -- decision ids,
    affected artifacts, plan items, action outcomes, remaining stale and
    blocking artifacts, audit reference and verification object -- and
    never touches decisions, artifacts or audits.
    Idempotent per lifecycle run (lifecycle_id); prior results are never
    overwritten; reads are side-effect free.
    """

    def __init__(self, store: AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultRawStore = None):
        self._store = (
            store if store is not None
            else InMemoryAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultRawStore()
        )

    def record(
        self, task_id: str, lifecycle_result
    ) -> AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultRecord:
        """Persist lifecycle_result for task_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultError:
                If task_id is not a non-empty string, lifecycle_result is
                missing or belongs to another task, or the store failed
        """
        self._require_text(task_id, "task_id")
        if lifecycle_result is None or lifecycle_result.task_id != task_id:
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultError(
                "lifecycle_result does not belong to the task_id given"
            )
        for existing in self._store.list_for_task(task_id):
            if existing.lifecycle_id == lifecycle_result.lifecycle_id:
                return existing

        verification = lifecycle_result.verification
        record = AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultRecord(
            task_id=task_id, lifecycle_id=lifecycle_result.lifecycle_id,
            operation_id=lifecycle_result.operation_id, status=lifecycle_result.status,
            authoritative_decision_id=lifecycle_result.authoritative_decision_id,
            previous_decision_id=lifecycle_result.previous_decision_id,
            affected_artifacts=tuple(lifecycle_result.affected_artifacts),
            planned_actions=tuple(lifecycle_result.planned_actions), applied=tuple(lifecycle_result.applied),
            skipped=tuple(lifecycle_result.skipped), failed=tuple(lifecycle_result.failed),
            remaining_stale=tuple(lifecycle_result.remaining_stale),
            blocking_artifacts=tuple(lifecycle_result.blocking_artifacts), audit_id=lifecycle_result.audit_id,
            verification=verification,
            verification_status=getattr(verification, "status", None) if verification is not None else None,
            errors=tuple(lifecycle_result.errors), completed_at=lifecycle_result.completed_at,
            recorded_at=datetime.now(timezone.utc),
        )
        try:
            return self._store.save(record)
        except Exception as error:
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultError(
                f"failed to persist lifecycle result {record.result_id!r}: {error}"
            ) from error

    def get(self, task_id: str, result_id: str):
        """task_id's exact result_id, or None if it does not exist for that task."""
        self._require_text(task_id, "task_id")
        self._require_text(result_id, "result_id")
        record = self._store.get(result_id)
        return record if record is not None and record.task_id == task_id else None

    def latest(self, task_id: str):
        """The most recently recorded result for task_id, or None."""
        history = self.history(task_id)
        return history[-1] if history else None

    def history(self, task_id: str) -> list:
        """Every lifecycle result recorded for task_id, oldest first."""
        self._require_text(task_id, "task_id")
        return self._store.list_for_task(task_id)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultError(
                f"{field_name} is required and must be a non-empty string"
            )
