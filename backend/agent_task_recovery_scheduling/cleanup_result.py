import json
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import NAMESPACE_OID, uuid5

from backend.storage import AtomicJsonFile

from .cleanup_batch import AgentTaskRecoveryScheduleCleanupBatchEntry, AgentTaskRecoveryScheduleCleanupBatchResult


class InvalidAgentTaskRecoveryScheduleCleanupResultError(ValueError):
    """Raised when record()/get()/history() is given invalid arguments,
    or a batch result that belongs to a different task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCleanupResultRecord:
    """Immutable, durable record of one batch cleanup: its counts, its
    per-schedule `entries` (outcome, reason, and failure error text, in
    processing order), `schedule_ids` (exactly the schedules that batch
    processed, same order), `executed_at` (when the batch ran) and
    `recorded_at` (when it was persisted).

    result_id is derived from the batch's own content (task_id,
    executed_at, entries), never random, so recording the same batch
    again lands on the same record."""

    result_id: str
    task_id: str
    executed_at: datetime
    recorded_at: datetime
    cleaned_count: int
    skipped_count: int
    failed_count: int
    entries: tuple
    schedule_ids: tuple

    def to_dict(self) -> dict:
        data = asdict(self)
        data["executed_at"] = self.executed_at.isoformat()
        data["recorded_at"] = self.recorded_at.isoformat()
        data["entries"] = [asdict(entry) for entry in self.entries]
        data["schedule_ids"] = list(self.schedule_ids)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryScheduleCleanupResultRecord":
        payload = dict(data)
        for key in ("executed_at", "recorded_at"):
            payload[key] = datetime.fromisoformat(payload[key])
        payload["entries"] = tuple(AgentTaskRecoveryScheduleCleanupBatchEntry(**e) for e in payload["entries"])
        payload["schedule_ids"] = tuple(payload["schedule_ids"])
        return cls(**payload)


class AgentTaskRecoveryScheduleCleanupResultStore(ABC):
    """Raw persistence for AgentTaskRecoveryScheduleCleanupResultRecord
    records -- this package's own established Store ABC + InMemory/Json
    shape (see the dispatch store)."""

    @abstractmethod
    def save(self, record: AgentTaskRecoveryScheduleCleanupResultRecord) -> AgentTaskRecoveryScheduleCleanupResultRecord:
        ...

    @abstractmethod
    def get(self, result_id: str) -> Optional[AgentTaskRecoveryScheduleCleanupResultRecord]:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


def _history_order(record: AgentTaskRecoveryScheduleCleanupResultRecord) -> tuple:
    return (record.executed_at, record.recorded_at, record.result_id)


class InMemoryAgentTaskRecoveryScheduleCleanupResultStore(AgentTaskRecoveryScheduleCleanupResultStore):
    """Stores cleanup result records in memory, for development and
    testing."""

    def __init__(self):
        self._by_id: dict = {}

    def save(self, record):
        self._by_id[record.result_id] = deepcopy(record)
        return deepcopy(record)

    def get(self, result_id):
        record = self._by_id.get(result_id)
        return deepcopy(record) if record is not None else None

    def list_for_task(self, task_id):
        return sorted((deepcopy(r) for r in self._by_id.values() if r.task_id == task_id), key=_history_order)


class JsonAgentTaskRecoveryScheduleCleanupResultStore(AgentTaskRecoveryScheduleCleanupResultStore):
    """Persists cleanup result records to a JSON file, keyed by
    result_id; the task_id lookup scans the (small) collection."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, record):
        records = self.file.read()
        records[record.result_id] = record.to_dict()
        self.file.write(records)
        return deepcopy(record)

    def get(self, result_id):
        data = self.file.read().get(result_id)
        return AgentTaskRecoveryScheduleCleanupResultRecord.from_dict(data) if data is not None else None

    def list_for_task(self, task_id):
        matching = [
            AgentTaskRecoveryScheduleCleanupResultRecord.from_dict(data)
            for data in self.file.read().values()
            if data.get("task_id") == task_id
        ]
        return sorted(matching, key=_history_order)


class LLMAgentTaskRecoveryPreflightScheduleCleanupResultService:
    """Keeps the outcome of each batch cleanup as durable maintenance
    history -- never a generic job-result store: it only stores the #8
    batch result's own fields, linked to the schedules it processed by
    their schedule_ids (the schedules themselves stay the source of
    truth for their state).

    Append-only: record() only ever adds. A batch whose content-derived
    result_id is already stored is returned as-is, first recorded_at
    standing, so recording it twice never duplicates or overwrites, and a
    different batch always gets its own record. get()/history() only
    read -- they never touch a schedule or run cleanup.
    """

    def __init__(self, store: AgentTaskRecoveryScheduleCleanupResultStore = None):
        self._store = store if store is not None else InMemoryAgentTaskRecoveryScheduleCleanupResultStore()

    def record(
        self, task_id: str, batch_result: AgentTaskRecoveryScheduleCleanupBatchResult
    ) -> AgentTaskRecoveryScheduleCleanupResultRecord:
        """
        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupResultError: If
                task_id is not a non-empty string, batch_result is not a
                batch cleanup result, or it is for a different task_id
        """
        self._require_text(task_id, "task_id")
        if not isinstance(batch_result, AgentTaskRecoveryScheduleCleanupBatchResult):
            raise InvalidAgentTaskRecoveryScheduleCleanupResultError(
                "batch_result must be an AgentTaskRecoveryScheduleCleanupBatchResult"
            )
        if batch_result.task_id != task_id:
            raise InvalidAgentTaskRecoveryScheduleCleanupResultError(
                f"batch_result belongs to task_id {batch_result.task_id!r}, not {task_id!r}"
            )

        fingerprint = json.dumps(
            [task_id, batch_result.executed_at.isoformat(), [asdict(e) for e in batch_result.entries]],
            sort_keys=True,
        )
        result_id = str(uuid5(NAMESPACE_OID, fingerprint))
        existing = self._store.get(result_id)
        if existing is not None:
            return existing

        return self._store.save(
            AgentTaskRecoveryScheduleCleanupResultRecord(
                result_id=result_id, task_id=task_id, executed_at=batch_result.executed_at,
                recorded_at=datetime.now(timezone.utc), cleaned_count=batch_result.cleaned_count,
                skipped_count=batch_result.skipped_count, failed_count=batch_result.failed_count,
                entries=tuple(batch_result.entries),
                schedule_ids=tuple(entry.schedule_id for entry in batch_result.entries),
            )
        )

    def get(self, task_id: str, result_id: str) -> Optional[AgentTaskRecoveryScheduleCleanupResultRecord]:
        """task_id's exact result_id, or None if it does not exist or
        belongs to a different task_id.

        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupResultError: If
                task_id or result_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(result_id, "result_id")
        record = self._store.get(result_id)
        return record if record is not None and record.task_id == task_id else None

    def history(self, task_id: str) -> tuple:
        """Every batch result ever recorded for task_id, oldest run
        first.

        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupResultError: If
                task_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        return tuple(self._store.list_for_task(task_id))

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleCleanupResultError(
                f"{field_name} is required and must be a non-empty string"
            )
