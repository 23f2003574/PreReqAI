from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional

from .models import AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord


class InvalidAgentTaskRecoveryExecutionDecisionFreshnessAuditError(ValueError):
    """Raised when record() is given invalid arguments, or freshness_result
    does not belong to the exact (task_id, decision_id) given."""


class AgentTaskRecoveryExecutionDecisionFreshnessAuditStore(ABC):
    """Raw persistence for AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord
    entries -- the same dual-index (audit_id, task_id), append-only shape
    Commit #12's own AgentTaskRecoveryExecutionPreconditionDecisionAuditStore
    already establishes. There is no update()/delete()."""

    @abstractmethod
    def save(
        self, record: AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord
    ) -> AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord:
        ...

    @abstractmethod
    def get(self, audit_id: str) -> Optional[AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord]:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore(
    AgentTaskRecoveryExecutionDecisionFreshnessAuditStore
):
    """Stores durable AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord
    entries in memory, for development and testing."""

    def __init__(self):
        self._by_id: dict = {}
        self._by_task: dict = {}

    def save(
        self, record: AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord
    ) -> AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord:
        stored = deepcopy(record)
        self._by_id[record.audit_id] = stored
        self._by_task.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def get(self, audit_id: str) -> Optional[AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord]:
        record = self._by_id.get(audit_id)
        return deepcopy(record) if record is not None else None

    def list_for_task(self, task_id: str) -> list:
        entries = self._by_task.get(task_id, [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.recorded_at)]


class LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService:
    """Records an immutable, append-only trail of every freshness
    evaluation -- fresh acceptance, stale/indeterminate rejection, and
    whether a Commit #4 revalidation was run -- never a second audit
    framework (Rule: "Do not create a second audit framework"): record()
    only ever accepts already-computed Commit #2/#4 result objects and
    persists their own fields verbatim through this class's own append-
    only store; it never calls check()/revalidate()/decide() itself, and
    never mutates the decision, authorization, or approval state it
    describes (Rule: "Never change the decision or trigger recovery").

    Idempotent for the same decision/evaluation event (Rule): before
    appending, checks whether the exact same (decision_id,
    freshness_status, freshness_reason, revalidation_action,
    replacement_decision_id) tuple was already recorded for this task --
    if so, returns that existing record unchanged rather than appending a
    duplicate. A genuinely different evaluation (e.g. fresh, then later
    stale) is always still appended -- this is deduplication of identical
    repeats, never a cap on history.
    """

    def __init__(self, store: AgentTaskRecoveryExecutionDecisionFreshnessAuditStore = None):
        """
        Args:
            store: Defaults to a fresh
                InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore.
        """
        self._store = store if store is not None else InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()

    def record(
        self, task_id: str, decision_id: str, freshness_result, revalidation_result=None
    ) -> AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord:
        """Record freshness_result (and, when given, revalidation_result)
        for task_id's exact decision_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionFreshnessAuditError:
                If task_id/decision_id is not a non-empty string, or
                freshness_result/revalidation_result does not belong to
                this exact (task_id, decision_id)
        """
        self._require_text(task_id, "task_id")
        self._require_text(decision_id, "decision_id")
        if freshness_result.task_id != task_id or freshness_result.decision_id != decision_id:
            raise InvalidAgentTaskRecoveryExecutionDecisionFreshnessAuditError(
                "freshness_result does not belong to the exact (task_id, decision_id) given"
            )
        if revalidation_result is not None and (
            revalidation_result.task_id != task_id or revalidation_result.old_decision_id != decision_id
        ):
            raise InvalidAgentTaskRecoveryExecutionDecisionFreshnessAuditError(
                "revalidation_result does not belong to the exact (task_id, decision_id) given"
            )

        revalidation_action = revalidation_result.action if revalidation_result is not None else None
        replacement_decision_id = None
        if (
            revalidation_result is not None
            and revalidation_result.new_decision_id is not None
            and revalidation_result.new_decision_id != decision_id
        ):
            replacement_decision_id = revalidation_result.new_decision_id

        signature = (
            freshness_result.status, freshness_result.reason, revalidation_action, replacement_decision_id
        )
        for existing in self._store.list_for_task(task_id):
            if existing.decision_id != decision_id:
                continue
            existing_signature = (
                existing.freshness_status, existing.freshness_reason, existing.revalidation_action,
                existing.replacement_decision_id,
            )
            if existing_signature == signature:
                return existing

        record = AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord(
            task_id=task_id, decision_id=decision_id, freshness_status=freshness_result.status,
            freshness_reason=freshness_result.reason,
            decision_state_version=freshness_result.decision_state_version,
            current_state_version=freshness_result.current_state_version,
            revalidated=revalidation_result is not None, revalidation_action=revalidation_action,
            replacement_decision_id=replacement_decision_id, recorded_at=self._now(),
        )
        return self._store.save(record)

    def get(self, audit_id: str) -> Optional[AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord]:
        """The exact audit_id's own record, or None if it does not exist.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionFreshnessAuditError:
                If audit_id is not a non-empty string
        """
        self._require_text(audit_id, "audit_id")
        return self._store.get(audit_id)

    def list(self, task_id: str) -> list:
        """Every freshness audit entry ever recorded for task_id, oldest
        to newest.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionFreshnessAuditError:
                If task_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        return self._store.list_for_task(task_id)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionFreshnessAuditError(
                f"{field_name} is required and must be a non-empty string"
            )
