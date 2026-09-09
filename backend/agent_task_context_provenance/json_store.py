from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import ContextProvenanceRecord
from .store import ProvenanceRecordStore


class JsonProvenanceRecordStore(ProvenanceRecordStore):
    """Persists context provenance history to a JSON file, keyed by task_id."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, record: ContextProvenanceRecord) -> ContextProvenanceRecord:
        by_task = self.file.read()
        records = by_task.setdefault(record.task_id, [])
        records.append(record.to_dict())
        self.file.write(by_task)
        return record

    def list_for_task(self, task_id: str) -> list:
        by_task = self.file.read()
        records = [ContextProvenanceRecord.from_dict(data) for data in by_task.get(task_id, [])]
        return sorted(records, key=lambda item: item.created_at)
