from abc import ABC, abstractmethod
from copy import deepcopy
from pathlib import Path
from typing import Optional

from backend.storage import AtomicJsonFile

from .models import AgentTaskRecoveryPreflight, AgentTaskRecoveryPreflightResult

# The AgentTaskRecoveryPreflight fields idempotency compares to decide "is
# this the same preflight already recorded" -- preflight_id/checked_at are
# this record's own bookkeeping (always new/fresh on a genuine repeat),
# never part of the comparison, the same "content is stable, bookkeeping
# moves" discipline backend.agent_task_event_analytics' own Commit #5/#9/#11
# already establish for their own content-based idempotency.
_IDENTITY_FIELDS = ("plan", "decision", "blocking_reasons", "warnings")


class InvalidAgentTaskRecoveryPreflightPersistenceError(ValueError):
    """Raised when save()/get()/history() is given invalid arguments."""


class AgentTaskRecoveryPreflightStore(ABC):
    """Raw persistence for the append-only record of every
    AgentTaskRecoveryPreflight ever saved for a task -- the same
    save()/list_for_task() split backend.agent_task_state_history.
    AgentTaskTransitionStore already uses for its own append-only trail.
    There is no update() or delete(): a preflight record is never
    overwritten or removed once recorded (Rule: "Preserve the original
    decision; never silently overwrite history")."""

    @abstractmethod
    def save(self, record: AgentTaskRecoveryPreflight) -> AgentTaskRecoveryPreflight:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryPreflightStore(AgentTaskRecoveryPreflightStore):
    """Stores durable AgentTaskRecoveryPreflight history records in
    memory, for development and testing."""

    def __init__(self):
        self._records: dict = {}

    def save(self, record: AgentTaskRecoveryPreflight) -> AgentTaskRecoveryPreflight:
        stored = deepcopy(record)
        self._records.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def list_for_task(self, task_id: str) -> list:
        records = self._records.get(task_id, [])
        return [deepcopy(record) for record in sorted(records, key=lambda item: item.checked_at)]


class JsonAgentTaskRecoveryPreflightStore(AgentTaskRecoveryPreflightStore):
    """Persists durable AgentTaskRecoveryPreflight history records to a
    JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, record: AgentTaskRecoveryPreflight) -> AgentTaskRecoveryPreflight:
        records = self.file.read()
        records.setdefault(record.task_id, []).append(record.to_dict())
        self.file.write(records)
        return deepcopy(record)

    def list_for_task(self, task_id: str) -> list:
        records = self.file.read()
        matching = [AgentTaskRecoveryPreflight.from_dict(data) for data in records.get(task_id, [])]
        return sorted(matching, key=lambda item: item.checked_at)


class LLMAgentTaskRecoveryPreflightStore:
    """Persists Commit #3's own AgentTaskRecoveryPreflightResult so
    execution/review workflows can inspect what was approved or blocked
    without rerunning the checks -- never a second orchestration or
    planning/guard layer (Rule: "Do not rerun guard/planning logic inside
    the store"; "Keep storage separate from Commit #3's orchestration"):
    save()/get()/history() only ever read/write through
    AgentTaskRecoveryPreflightStore's own append-only save()/
    list_for_task() -- nothing here calls the planner, the guard, or
    Commit #2's evaluation service.

    Persists preflight results, never task state (Rule): the underlying
    store only ever holds AgentTaskRecoveryPreflight records, and nothing
    this class does ever touches backend.agent_task_lifecycle/
    agent_task_events or any other authoritative task-state store.

    Append-only, never overwritten (Rule: "Preserve the original decision;
    never silently overwrite history"): every genuinely new save() adds
    one more entry to task_id's own history; there is no update()/
    delete() anywhere in this class or the store it wraps.

    save() is idempotent for the same preflight content (Rule: "Saving
    the same preflight must be idempotent where existing IDs allow it"):
    before appending anything, it checks task_id's already-saved history
    for one whose own plan/decision/blocking_reasons/warnings all already
    match -- if found, that existing record (with its own already-minted
    preflight_id) is returned unchanged rather than appending a
    duplicate. This is the same content-based idempotency convention
    backend.agent_task_event_analytics' own Commit #5/#9/#11 already
    establish, applied here to a preflight snapshot instead.

    get()/history() are both plain, deterministic reads through
    list_for_task() (Rule: "Retrieval is deterministic" -- inherited
    directly from the underlying store's own already-deterministic,
    checked_at-sorted ordering); get() never raises for a missing
    task_id, returning None instead -- the same tolerant-read discipline
    every other read path in this project's own task family already
    establishes. history(limit=...) caps to the most recent entries,
    still oldest to newest -- the same convention this project's own
    event/history services already use.
    """

    def __init__(self, store: AgentTaskRecoveryPreflightStore = None):
        self._store = store if store is not None else InMemoryAgentTaskRecoveryPreflightStore()

    def save(self, preflight: AgentTaskRecoveryPreflightResult) -> AgentTaskRecoveryPreflight:
        """Persist preflight's own useful decision context for its
        task_id. Idempotent: an already-saved, content-identical
        preflight is returned unchanged rather than duplicated.

        Raises:
            InvalidAgentTaskRecoveryPreflightPersistenceError: If
                preflight is not an AgentTaskRecoveryPreflightResult
        """
        if not isinstance(preflight, AgentTaskRecoveryPreflightResult):
            raise InvalidAgentTaskRecoveryPreflightPersistenceError(
                "preflight must be an AgentTaskRecoveryPreflightResult"
            )

        candidate = AgentTaskRecoveryPreflight(
            task_id=preflight.task_id,
            plan=preflight.plan,
            decision=preflight.decision,
            blocking_reasons=preflight.blocking_reasons,
            warnings=preflight.warnings,
            checked_at=preflight.checked_at,
        )

        existing = self._find_matching(preflight.task_id, candidate)
        if existing is not None:
            return existing

        return self._store.save(candidate)

    def get(self, task_id: str) -> Optional[AgentTaskRecoveryPreflight]:
        """task_id's most recently saved preflight, or None when nothing
        has ever been saved for it.

        Raises:
            InvalidAgentTaskRecoveryPreflightPersistenceError: If task_id
                is not a non-empty string
        """
        self._require_text(task_id)
        records = self.history(task_id)
        return records[-1] if records else None

    def history(self, task_id: str, limit: int = None) -> list:
        """Every preflight ever saved for task_id, oldest to newest,
        optionally capped to the most recent limit entries (still
        returned oldest to newest).

        Raises:
            InvalidAgentTaskRecoveryPreflightPersistenceError: If task_id
                is not a non-empty string, or limit is given and is not a
                non-negative int
        """
        self._require_text(task_id)
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 0):
            raise InvalidAgentTaskRecoveryPreflightPersistenceError("limit must be a non-negative int when given")

        records = self._store.list_for_task(task_id)
        if limit is not None:
            records = records[-limit:] if limit > 0 else []
        return records

    def _find_matching(self, task_id: str, candidate: AgentTaskRecoveryPreflight) -> Optional[AgentTaskRecoveryPreflight]:
        for record in self._store.list_for_task(task_id):
            if all(getattr(record, field) == getattr(candidate, field) for field in _IDENTITY_FIELDS):
                return record
        return None

    @staticmethod
    def _require_text(value, field_name: str = "task_id") -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightPersistenceError(
                f"{field_name} is required and must be a non-empty string"
            )
