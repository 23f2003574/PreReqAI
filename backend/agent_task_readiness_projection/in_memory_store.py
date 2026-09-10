from copy import deepcopy

from .models import AgentTaskReadinessProjection
from .store import AgentTaskReadinessProjectionStore


class InMemoryAgentTaskReadinessProjectionStore(AgentTaskReadinessProjectionStore):
    """Stores the latest AgentTaskReadinessProjection per task_id in
    memory, for development and testing."""

    def __init__(self):
        self._projections: dict[str, AgentTaskReadinessProjection] = {}

    def save(self, projection: AgentTaskReadinessProjection) -> AgentTaskReadinessProjection:
        stored = deepcopy(projection)
        self._projections[projection.task_id] = stored
        return deepcopy(stored)

    def get(self, task_id: str):
        projection = self._projections.get(task_id)
        return deepcopy(projection) if projection is not None else None
