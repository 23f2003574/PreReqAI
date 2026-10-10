from abc import ABC, abstractmethod
from typing import Optional

from .models import TaskContextSnapshot


class TaskContextSnapshotStore(ABC):
    """Persistence for immutable TaskContextSnapshot history.

    Same save/get/list_for_task/latest_for_task shape backend.llm.
    context_version.LLMContextVersionStore already establishes for an
    immutable, monotonically-versioned record -- there is no update() or
    delete(): a snapshot, once saved, is never replaced (Rule:
    "snapshots are immutable").
    """

    @abstractmethod
    def save(self, snapshot: TaskContextSnapshot) -> TaskContextSnapshot:
        ...

    @abstractmethod
    def get(self, snapshot_id: str) -> Optional[TaskContextSnapshot]:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...

    @abstractmethod
    def latest_for_task(self, task_id: str) -> Optional[TaskContextSnapshot]:
        ...
