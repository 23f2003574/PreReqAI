from copy import deepcopy

from .models import AgentTaskEventProjection
from .projection_store import AgentTaskEventProjectionStore


class InMemoryAgentTaskEventProjectionStore(AgentTaskEventProjectionStore):
    """Stores the latest AgentTaskEventProjection per task_id in memory,
    for development and testing."""

    def __init__(self):
        self._projections: dict[str, AgentTaskEventProjection] = {}

    def save(self, projection: AgentTaskEventProjection) -> AgentTaskEventProjection:
        stored = deepcopy(projection)
        self._projections[projection.task_id] = stored
        return deepcopy(stored)

    def get(self, task_id: str):
        projection = self._projections.get(task_id)
        return deepcopy(projection) if projection is not None else None
