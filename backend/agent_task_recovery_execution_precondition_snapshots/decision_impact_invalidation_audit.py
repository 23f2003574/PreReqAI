from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone

from .models import (
    ARTIFACT_STALE,
    AgentTaskRecoveryExecutionDecisionImpactInvalidationAuditRecord,
)


class InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditError(ValueError):
    """Raised when record() is given invalid arguments or a result for
    another task."""


class AgentTaskRecoveryExecutionDecisionImpactInvalidationAuditStore(ABC):
    """Raw, append-only persistence for impact-invalidation audit records
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


class InMemoryAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditStore(
    AgentTaskRecoveryExecutionDecisionImpactInvalidationAuditStore
):
    """In-memory impact-invalidation audit storage, for development and
    testing."""

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


class LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService:
    """Records exactly what an impact-invalidation operation (#5) did --
    applied, skipped (including manual review) and failed artifacts, the
    artifacts' states before execution, and what is still stale or
    blocking afterwards -- following the package's append-only audit and
    schema_version conventions. record() only copies the execution result
    verbatim and never touches an artifact. Idempotent per operation_id.
    """

    def __init__(self, store: AgentTaskRecoveryExecutionDecisionImpactInvalidationAuditStore = None):
        self._store = store or InMemoryAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditStore()

    def record(self, task_id: str, invalidation_result) -> AgentTaskRecoveryExecutionDecisionImpactInvalidationAuditRecord:
        """Record invalidation_result for task_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditError:
                If task_id is not a non-empty string, or
                invalidation_result is missing or belongs to another task
        """
        self._require_text(task_id, "task_id")
        if invalidation_result is None or invalidation_result.task_id != task_id:
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditError(
                "invalidation_result does not belong to the task_id given"
            )
        for existing in self._store.list_for_task(task_id):
            if existing.operation_id == invalidation_result.operation_id:
                return existing

        outcomes = invalidation_result.applied + invalidation_result.skipped + invalidation_result.failed
        artifact_ids = []
        for artifact_id in [o.artifact_id for o in outcomes] + list(invalidation_result.still_blocking):
            if artifact_id not in artifact_ids:
                artifact_ids.append(artifact_id)
        before = invalidation_result.initial_staleness
        after = invalidation_result.final_staleness
        previous_states = tuple(
            (f"{a.kind}:{a.reference}", a.status) for a in (before.artifacts if before is not None else ())
            if f"{a.kind}:{a.reference}" in artifact_ids
        )
        record = AgentTaskRecoveryExecutionDecisionImpactInvalidationAuditRecord(
            task_id=task_id, operation_id=invalidation_result.operation_id,
            previous_decision_id=invalidation_result.previous_decision_id,
            current_decision_id=invalidation_result.current_decision_id, artifact_ids=tuple(artifact_ids),
            previous_artifact_states=previous_states, applied=tuple(invalidation_result.applied),
            skipped=tuple(invalidation_result.skipped),
            manual_review=tuple(o for o in invalidation_result.skipped if o.action == "manual_review"),
            failed=tuple(invalidation_result.failed),
            remaining_stale=tuple(
                f"{a.kind}:{a.reference}" for a in (after.artifacts if after is not None else ())
                if a.status == ARTIFACT_STALE
            ),
            still_blocking=tuple(invalidation_result.still_blocking), plan_valid=invalidation_result.plan_valid,
            plan_issues=tuple(invalidation_result.plan_issues),
            pre_staleness_status=before.status if before is not None else None,
            post_staleness_status=after.status if after is not None else None,
            executed_at=invalidation_result.executed_at, recorded_at=datetime.now(timezone.utc),
        )
        return self._store.save(record)

    def get(self, audit_id: str):
        """The exact audit_id's record, or None."""
        self._require_text(audit_id, "audit_id")
        return self._store.get(audit_id)

    def list(self, task_id: str) -> list:
        """Every impact-invalidation audit record for task_id, oldest first."""
        self._require_text(task_id, "task_id")
        return self._store.list_for_task(task_id)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditError(
                f"{field_name} is required and must be a non-empty string"
            )
