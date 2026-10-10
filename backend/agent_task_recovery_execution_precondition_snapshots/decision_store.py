from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Optional

from .models import AgentTaskRecoveryExecutionPreconditionDecision


class InvalidAgentTaskRecoveryExecutionPreconditionDecisionPersistenceError(RuntimeError):
    """Raised when save()/get()/latest()/history() is given invalid
    arguments, or when the underlying raw store raises while persisting a
    decision -- deliberately a RuntimeError, not a ValueError, since a
    save() failure here is an operational persistence failure, not a bad
    caller input (Rule: "Persistence failure must not silently turn an
    allow into an unsafe execution")."""


class AgentTaskRecoveryExecutionPreconditionDecisionRawStore(ABC):
    """Raw persistence for AgentTaskRecoveryExecutionPreconditionDecision
    records -- indexed both by decision_id (get()'s own lookup key) and by
    task_id (list_for_task(), the same dual-index shape Commit #1's own
    AgentTaskRecoveryExecutionPreconditionSnapshotStore already
    establishes). There is no update()/delete(): a decision is never
    overwritten or removed once recorded (Rule: "Preserve historical
    decisions; never overwrite an earlier decision")."""

    @abstractmethod
    def save(
        self, record: AgentTaskRecoveryExecutionPreconditionDecision
    ) -> AgentTaskRecoveryExecutionPreconditionDecision:
        ...

    @abstractmethod
    def get(self, decision_id: str) -> Optional[AgentTaskRecoveryExecutionPreconditionDecision]:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryExecutionPreconditionDecisionRawStore(
    AgentTaskRecoveryExecutionPreconditionDecisionRawStore
):
    """Stores durable AgentTaskRecoveryExecutionPreconditionDecision
    records in memory, for development and testing. A JSON-backed store
    is deliberately not provided in this commit (Rule: "Keep this commit
    strictly about decision persistence"): validation_result/
    drift_classification/approval_reconciliation nest Commits #2-#5's own
    result objects, none of which were built with to_dict()/from_dict()
    round-tripping (they were designed as purely computed, in-process
    results) -- adding that would be a second, much larger commit's worth
    of work across four other modules, not this one."""

    def __init__(self):
        self._by_id: dict = {}
        self._by_task: dict = {}

    def save(
        self, record: AgentTaskRecoveryExecutionPreconditionDecision
    ) -> AgentTaskRecoveryExecutionPreconditionDecision:
        stored = deepcopy(record)
        self._by_id[record.decision_id] = stored
        self._by_task.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def get(self, decision_id: str) -> Optional[AgentTaskRecoveryExecutionPreconditionDecision]:
        record = self._by_id.get(decision_id)
        return deepcopy(record) if record is not None else None

    def list_for_task(self, task_id: str) -> list:
        entries = self._by_task.get(task_id, [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.created_at)]


class LLMAgentTaskRecoveryExecutionPreconditionDecisionStore:
    """Persists every Commit #6 AgentTaskRecoveryExecutionPreconditionDecision
    ever computed for a task, so the system has an immutable record of
    what evidence led to allow/review/block -- never a new database/
    repository framework (Rule): save()/get()/latest()/history() only
    ever read/write through an AgentTaskRecoveryExecutionPreconditionDecisionRawStore's
    own save()/get()/list_for_task(), the same append-only discipline
    every other snapshot/history store in this package already
    establishes.

    Never responsible for recomputing a decision (Rule: "Do not make the
    store responsible for recomputing decisions"): save() only ever
    accepts an already-computed AgentTaskRecoveryExecutionPreconditionDecision
    and persists it verbatim -- nothing here calls decide() or any other
    precondition service.

    Preserves complete, immutable history (Rule): the underlying raw
    store has no update()/delete() at all, so repeated evaluation for the
    same task_id always appends a new record, never mutates or replaces
    an earlier one. latest() is exactly history()'s own last entry (the
    raw store's list_for_task() is sorted by created_at); history() is
    every decision ever recorded for task_id, oldest to newest.
    """

    def __init__(self, store: AgentTaskRecoveryExecutionPreconditionDecisionRawStore = None):
        """
        Args:
            store: Defaults to a fresh
                InMemoryAgentTaskRecoveryExecutionPreconditionDecisionRawStore.
        """
        self._store = store if store is not None else InMemoryAgentTaskRecoveryExecutionPreconditionDecisionRawStore()

    def save(
        self, decision: AgentTaskRecoveryExecutionPreconditionDecision
    ) -> AgentTaskRecoveryExecutionPreconditionDecision:
        """Persist decision verbatim.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionDecisionPersistenceError:
                If decision is not an
                AgentTaskRecoveryExecutionPreconditionDecision, or the
                underlying store raised while saving it
        """
        if not isinstance(decision, AgentTaskRecoveryExecutionPreconditionDecision):
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionPersistenceError(
                "decision must be an AgentTaskRecoveryExecutionPreconditionDecision"
            )
        try:
            return self._store.save(decision)
        except Exception as error:
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionPersistenceError(
                f"failed to persist decision {decision.decision_id!r}: {error}"
            ) from error

    def get(self, decision_id: str) -> Optional[AgentTaskRecoveryExecutionPreconditionDecision]:
        """The exact decision_id's own record, or None if it does not
        exist.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionDecisionPersistenceError:
                If decision_id is not a non-empty string
        """
        self._require_text(decision_id, "decision_id")
        return self._store.get(decision_id)

    def latest(self, task_id: str) -> Optional[AgentTaskRecoveryExecutionPreconditionDecision]:
        """The most recently saved decision for task_id, or None if none
        has ever been recorded.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionDecisionPersistenceError:
                If task_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        history = self._store.list_for_task(task_id)
        return history[-1] if history else None

    def history(self, task_id: str) -> list:
        """Every decision ever recorded for task_id, oldest to newest.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionDecisionPersistenceError:
                If task_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        return self._store.list_for_task(task_id)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionPersistenceError(
                f"{field_name} is required and must be a non-empty string"
            )
