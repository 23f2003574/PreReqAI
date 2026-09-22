from abc import ABC, abstractmethod
from copy import deepcopy
from pathlib import Path
from typing import Optional

from backend.storage import AtomicJsonFile

from .models import AgentTaskRecoveryExecutionPreconditionSnapshot


class AgentTaskRecoveryExecutionPreconditionSnapshotStore(ABC):
    """Raw persistence for AgentTaskRecoveryExecutionPreconditionSnapshot
    records -- indexed both by snapshot_id (get()'s own lookup key, used
    by compare()) and by task_id (list_for_task()), the same dual-index
    shape backend.agent_task_recovery_preflight_dependency_snapshots' own
    AgentTaskRecoveryPreflightDependencySnapshotStore already establishes
    for a comparable case. There is no update()/delete(): a snapshot is
    never overwritten or removed once recorded (Rule: "Immutable after
    creation")."""

    @abstractmethod
    def save(
        self, record: AgentTaskRecoveryExecutionPreconditionSnapshot
    ) -> AgentTaskRecoveryExecutionPreconditionSnapshot:
        ...

    @abstractmethod
    def get(self, snapshot_id: str) -> Optional[AgentTaskRecoveryExecutionPreconditionSnapshot]:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryExecutionPreconditionSnapshotStore(AgentTaskRecoveryExecutionPreconditionSnapshotStore):
    """Stores durable AgentTaskRecoveryExecutionPreconditionSnapshot
    records in memory, for development and testing."""

    def __init__(self):
        self._by_id: dict = {}
        self._by_task: dict = {}

    def save(
        self, record: AgentTaskRecoveryExecutionPreconditionSnapshot
    ) -> AgentTaskRecoveryExecutionPreconditionSnapshot:
        stored = deepcopy(record)
        self._by_id[record.snapshot_id] = stored
        self._by_task.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def get(self, snapshot_id: str) -> Optional[AgentTaskRecoveryExecutionPreconditionSnapshot]:
        record = self._by_id.get(snapshot_id)
        return deepcopy(record) if record is not None else None

    def list_for_task(self, task_id: str) -> list:
        entries = self._by_task.get(task_id, [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.captured_at)]


class JsonAgentTaskRecoveryExecutionPreconditionSnapshotStore(AgentTaskRecoveryExecutionPreconditionSnapshotStore):
    """Persists durable AgentTaskRecoveryExecutionPreconditionSnapshot
    records to a JSON file, keyed by snapshot_id; the task_id lookup
    scans the (small) collection rather than maintaining a second
    on-disk index -- the same shape backend.
    agent_task_recovery_preflight_dependency_snapshots' own
    JsonAgentTaskRecoveryPreflightDependencySnapshotStore already uses
    for a comparable case."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(
        self, record: AgentTaskRecoveryExecutionPreconditionSnapshot
    ) -> AgentTaskRecoveryExecutionPreconditionSnapshot:
        records = self.file.read()
        records[record.snapshot_id] = record.to_dict()
        self.file.write(records)
        return deepcopy(record)

    def get(self, snapshot_id: str) -> Optional[AgentTaskRecoveryExecutionPreconditionSnapshot]:
        data = self.file.read().get(snapshot_id)
        return AgentTaskRecoveryExecutionPreconditionSnapshot.from_dict(data) if data is not None else None

    def list_for_task(self, task_id: str) -> list:
        matching = [
            AgentTaskRecoveryExecutionPreconditionSnapshot.from_dict(data)
            for data in self.file.read().values()
            if data.get("task_id") == task_id
        ]
        return sorted(matching, key=lambda item: item.captured_at)
