from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional

from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .models import AgentTaskRecoveryExecutionPreconditionDecisionAuditRecord


class InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditError(ValueError):
    """Raised when record()/get()/list() is given invalid arguments, or
    decision_id names no decision recorded for task_id."""


class AgentTaskRecoveryExecutionPreconditionDecisionAuditStore(ABC):
    """Raw persistence for AgentTaskRecoveryExecutionPreconditionDecisionAuditRecord
    entries -- indexed both by audit_id (get()'s own lookup key) and by
    task_id (list_for_task()), the same dual-index shape Commit #1's own
    AgentTaskRecoveryExecutionPreconditionSnapshotStore already
    establishes. There is no update()/delete(): an audit entry is never
    overwritten or removed once recorded (Rule: "Audit records are
    append-only; never mutate historical entries")."""

    @abstractmethod
    def save(
        self, record: AgentTaskRecoveryExecutionPreconditionDecisionAuditRecord
    ) -> AgentTaskRecoveryExecutionPreconditionDecisionAuditRecord:
        ...

    @abstractmethod
    def get(self, audit_id: str) -> Optional[AgentTaskRecoveryExecutionPreconditionDecisionAuditRecord]:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryExecutionPreconditionDecisionAuditStore(
    AgentTaskRecoveryExecutionPreconditionDecisionAuditStore
):
    """Stores durable AgentTaskRecoveryExecutionPreconditionDecisionAuditRecord
    entries in memory, for development and testing."""

    def __init__(self):
        self._by_id: dict = {}
        self._by_task: dict = {}

    def save(
        self, record: AgentTaskRecoveryExecutionPreconditionDecisionAuditRecord
    ) -> AgentTaskRecoveryExecutionPreconditionDecisionAuditRecord:
        stored = deepcopy(record)
        self._by_id[record.audit_id] = stored
        self._by_task.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def get(self, audit_id: str) -> Optional[AgentTaskRecoveryExecutionPreconditionDecisionAuditRecord]:
        record = self._by_id.get(audit_id)
        return deepcopy(record) if record is not None else None

    def list_for_task(self, task_id: str) -> list:
        entries = self._by_task.get(task_id, [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.recorded_at)]


class LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService:
    """Records an immutable audit trail of which Commit #7-persisted
    decision was acted upon, against what evidence, and when -- never a
    second audit framework (Rule: "Do not invent a new audit framework";
    "Reuse existing audit storage/model conventions where available" --
    the same append-only save()/get()/list_for_task() shape every other
    history store in this package already uses).

    Audits persisted decisions, never raw/recomputed state (Rule): record()
    only ever reads decision_id through Commit #7's own decision store --
    it never calls validate()/classify()/reconcile()/decide() itself, and
    never mutates the decision it audits (Rule: "Recording an audit entry
    must not modify the decision itself").

    Kept separate from Commit #11's own operational report (Rule): this
    class answers "what decision was made, against which evidence, and
    when, and who/what triggered recording it" -- a durable, append-only
    evidentiary trail, never a live, recomputed-on-read summary the way
    Commit #11's report() is.
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        store: AgentTaskRecoveryExecutionPreconditionDecisionAuditStore = None,
    ):
        """
        Args:
            decision_store: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionStore;
                pass the real instance holding the decisions decide()
                actually persisted.
            store: Defaults to a fresh
                InMemoryAgentTaskRecoveryExecutionPreconditionDecisionAuditStore.
        """
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        self._store = store if store is not None else InMemoryAgentTaskRecoveryExecutionPreconditionDecisionAuditStore()

    def record(
        self, task_id: str, decision_id: str, actor: str = None, operation_id: str = None
    ) -> AgentTaskRecoveryExecutionPreconditionDecisionAuditRecord:
        """Record an immutable audit entry for task_id's exact,
        already-persisted decision_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditError:
                If task_id/decision_id is not a non-empty string, actor/
                operation_id is given but is not a string, or decision_id
                names no decision recorded for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(decision_id, "decision_id")
        if actor is not None and not isinstance(actor, str):
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditError("actor must be a string when given")
        if operation_id is not None and not isinstance(operation_id, str):
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditError(
                "operation_id must be a string when given"
            )

        decision = self._decision_store.get(decision_id)
        if decision is None or decision.task_id != task_id:
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditError(
                f"no decision {decision_id!r} is recorded for task_id {task_id!r}"
            )

        record = AgentTaskRecoveryExecutionPreconditionDecisionAuditRecord(
            task_id=task_id,
            decision_id=decision_id,
            decision=decision.decision,
            snapshot_id=decision.snapshot_id,
            authorization_id=decision.authorization_id,
            reason=decision.reason,
            blocking_conditions=decision.blocking_conditions,
            warnings=decision.warnings,
            actor=actor,
            operation_id=operation_id,
            recorded_at=self._now(),
        )
        return self._store.save(record)

    def get(self, audit_id: str) -> Optional[AgentTaskRecoveryExecutionPreconditionDecisionAuditRecord]:
        """The exact audit_id's own record, or None if it does not exist.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditError:
                If audit_id is not a non-empty string
        """
        self._require_text(audit_id, "audit_id")
        return self._store.get(audit_id)

    def list(self, task_id: str) -> list:
        """Every audit entry ever recorded for task_id, oldest to newest.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditError:
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
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditError(
                f"{field_name} is required and must be a non-empty string"
            )
