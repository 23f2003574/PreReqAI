from copy import deepcopy
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import AgentTaskReadinessProjection
from .store import AgentTaskReadinessProjectionStore


class JsonAgentTaskReadinessProjectionStore(AgentTaskReadinessProjectionStore):
    """Persists the latest AgentTaskReadinessProjection per task_id to a
    JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, projection: AgentTaskReadinessProjection) -> AgentTaskReadinessProjection:
        projections = self.file.read()
        projections[projection.task_id] = projection.to_dict()
        self.file.write(projections)
        return deepcopy(projection)

    def get(self, task_id: str):
        projections = self.file.read()
        data = projections.get(task_id)
        return None if data is None else AgentTaskReadinessProjection.from_dict(data)
