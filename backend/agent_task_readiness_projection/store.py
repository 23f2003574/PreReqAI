from abc import ABC, abstractmethod
from typing import Optional

from .models import AgentTaskReadinessProjection


class AgentTaskReadinessProjectionStore(ABC):
    """Persistence for the single latest AgentTaskReadinessProjection
    per task_id -- mirrors backend.agent_task_lifecycle.AgentTaskStore's
    own save/get shape exactly (Rule: "reuse the repository's existing
    projection/state-storage patterns"), not an append-only trail:
    save() always replaces whatever was stored for that task_id before
    (Behavior 3: "replace older projection for the same task rather
    than accumulating duplicate current-state records").
    """

    @abstractmethod
    def save(self, projection: AgentTaskReadinessProjection) -> AgentTaskReadinessProjection:
        ...

    @abstractmethod
    def get(self, task_id: str) -> Optional[AgentTaskReadinessProjection]:
        ...
