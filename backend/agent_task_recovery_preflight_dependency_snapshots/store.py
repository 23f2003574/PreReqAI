from abc import ABC, abstractmethod
from copy import deepcopy
from pathlib import Path
from typing import Optional

from backend.storage import AtomicJsonFile

from .models import AgentTaskRecoveryPreflightDependencySnapshot


class AgentTaskRecoveryPreflightDependencySnapshotStore(ABC):
    """Raw persistence for AgentTaskRecoveryPreflightDependencySnapshot
    records -- indexed both by snapshot_id (get()'s own lookup key, used
    by diff()) and by task_id (list_for_task()), the same dual-index
    shape backend.agent_task_recovery_scheduling's own
    AgentTaskRecoveryScheduleStore already establishes for a comparable
    case. There is no update()/delete(): a snapshot is never overwritten
    or removed once recorded (Rule: "Preserve immutable snapshots")."""

    @abstractmethod
    def save(self, record: AgentTaskRecoveryPreflightDependencySnapshot) -> AgentTaskRecoveryPreflightDependencySnapshot:
        ...

    @abstractmethod
    def get(self, snapshot_id: str) -> Optional[AgentTaskRecoveryPreflightDependencySnapshot]:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryPreflightDependencySnapshotStore(AgentTaskRecoveryPreflightDependencySnapshotStore):
    """Stores durable AgentTaskRecoveryPreflightDependencySnapshot
    records in memory, for development and testing."""

    def __init__(self):
        self._by_id: dict = {}
        self._by_task: dict = {}

    def save(
        self, record: AgentTaskRecoveryPreflightDependencySnapshot
    ) -> AgentTaskRecoveryPreflightDependencySnapshot:
        stored = deepcopy(record)
        self._by_id[record.snapshot_id] = stored
        self._by_task.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def get(self, snapshot_id: str) -> Optional[AgentTaskRecoveryPreflightDependencySnapshot]:
        record = self._by_id.get(snapshot_id)
        return deepcopy(record) if record is not None else None

    def list_for_task(self, task_id: str) -> list:
        entries = self._by_task.get(task_id, [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.captured_at)]


class JsonAgentTaskRecoveryPreflightDependencySnapshotStore(AgentTaskRecoveryPreflightDependencySnapshotStore):
    """Persists durable AgentTaskRecoveryPreflightDependencySnapshot
    records to a JSON file, keyed by snapshot_id; the task_id lookup
    scans the (small) collection rather than maintaining a second
    on-disk index -- the same shape backend.agent_task_recovery_scheduling's
    own JsonAgentTaskRecoveryScheduleStore already uses for a comparable
    case."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(
        self, record: AgentTaskRecoveryPreflightDependencySnapshot
    ) -> AgentTaskRecoveryPreflightDependencySnapshot:
        records = self.file.read()
        records[record.snapshot_id] = record.to_dict()
        self.file.write(records)
        return deepcopy(record)

    def get(self, snapshot_id: str) -> Optional[AgentTaskRecoveryPreflightDependencySnapshot]:
        data = self.file.read().get(snapshot_id)
        return AgentTaskRecoveryPreflightDependencySnapshot.from_dict(data) if data is not None else None

    def list_for_task(self, task_id: str) -> list:
        matching = [
            AgentTaskRecoveryPreflightDependencySnapshot.from_dict(data)
            for data in self.file.read().values()
            if data.get("task_id") == task_id
        ]
        return sorted(matching, key=lambda item: item.captured_at)
