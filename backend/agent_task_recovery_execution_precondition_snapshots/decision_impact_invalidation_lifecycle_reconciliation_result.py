from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional

from .models import AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultRecord


class InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultError(ValueError):
    """Raised when record()/get()/latest()/history() is given invalid
    arguments, or the reconciliation result belongs to another task."""


class AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultRawStore(ABC):
    """Raw, append-only persistence for lifecycle reconciliation result
    records -- the same dual-index (result_id, task_id) shape as the
    lifecycle result store. There is no update()/delete()."""

    @abstractmethod
    def save(self, record):
        ...

    @abstractmethod
    def get(self, result_id: str):
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultRawStore(
    AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultRawStore
):
    """In-memory lifecycle reconciliation result storage, for development and testing.
    save() never replaces an existing result_id."""

    def __init__(self):
        self._by_id: dict = {}
        self._by_task: dict = {}

    def save(self, record):
        if record.result_id in self._by_id:
            raise ValueError(f"reconciliation result {record.result_id!r} already exists")
        stored = deepcopy(record)
        self._by_id[record.result_id] = stored
        self._by_task.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def get(self, result_id: str):
        record = self._by_id.get(result_id)
        return deepcopy(record) if record is not None else None

    def list_for_task(self, task_id: str) -> list:
        return [deepcopy(entry) for entry in self._by_task.get(task_id, [])]


class LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultService:
    """Persists each lifecycle reconciliation (#11) so obsolete remediation
    lifecycles form an explicit historical chain -- previous result ->
    replacement result -- instead of overwriting anything. A dedicated
    append-only store for this one record type, following #9's
    result persistence conventions (schema_version, get/latest/history,
    to_dict), not a generic reconciliation store.

    record() copies the reconciliation result verbatim; neither the
    original nor the replacement lifecycle result is touched. Idempotent
    per reconciliation_id; latest() is the newest recorded reconciliation
    state; reads are side-effect free.
    """

    def __init__(self, store: AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultRawStore = None):
        self._store = (
            store if store is not None
            else InMemoryAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultRawStore()
        )

    def record(
        self, task_id: str, reconciliation_result
    ) -> AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultRecord:
        """Persist reconciliation_result for task_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultError:
                If task_id is not a non-empty string, reconciliation_result is
                missing or belongs to another task, or the store failed
        """
        self._require_text(task_id, "task_id")
        if reconciliation_result is None or reconciliation_result.task_id != task_id:
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultError(
                "reconciliation_result does not belong to the task_id given"
            )
        for existing in self._store.list_for_task(task_id):
            if existing.reconciliation_id == reconciliation_result.reconciliation_id:
                return existing

        r = reconciliation_result
        record = AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultRecord(
            task_id=task_id, reconciliation_id=r.reconciliation_id, previous_result_id=r.previous_result_id,
            previous_status=r.previous_status, state=r.state, current_decision_id=r.current_decision_id,
            newly_stale_artifacts=tuple(r.newly_stale_artifacts), replacement_result_id=r.replacement_result_id,
            replacement_operation_id=r.replacement_operation_id, unresolved_blockers=tuple(r.unresolved_blockers),
            verification_status=r.final_verification_status, issues=tuple(r.issues), reconciled_at=r.reconciled_at,
            recorded_at=datetime.now(timezone.utc),
        )
        try:
            return self._store.save(record)
        except Exception as error:
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultError(
                f"failed to persist reconciliation result {record.result_id!r}: {error}"
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
        """Every reconciliation recorded for task_id, oldest first."""
        self._require_text(task_id, "task_id")
        return self._store.list_for_task(task_id)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultError(
                f"{field_name} is required and must be a non-empty string"
            )
