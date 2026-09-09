from copy import deepcopy

from .models import ContextProvenanceRecord
from .store import ProvenanceRecordStore


class InMemoryProvenanceRecordStore(ProvenanceRecordStore):
    """Stores context provenance history in memory, for development and testing."""

    def __init__(self):
        self._records_by_task: dict[str, list] = {}

    def save(self, record: ContextProvenanceRecord) -> ContextProvenanceRecord:
        stored = deepcopy(record)
        self._records_by_task.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def list_for_task(self, task_id: str) -> list:
        records = self._records_by_task.get(task_id, [])
        return [deepcopy(record) for record in sorted(records, key=lambda item: item.created_at)]
