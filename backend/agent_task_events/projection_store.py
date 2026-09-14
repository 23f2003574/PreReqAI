from abc import ABC, abstractmethod
from typing import Optional

from .models import AgentTaskEventProjection


class AgentTaskEventProjectionStore(ABC):
    """Persistence for the single latest AgentTaskEventProjection per
    task_id -- mirrors backend.agent_task_readiness_projection.
    AgentTaskReadinessProjectionStore's own save()/get() shape exactly,
    the closest existing projection/read-model pattern in this repository
    (Rule: "Do not invent a new persistence abstraction if an existing one
    fits"). Not an append-only trail: save() always replaces whatever was
    stored for that task_id before -- there is only ever one *current*
    projection per task_id, never a history of past ones (Commit #2's own
    AgentTaskEvent stream already owns that shape, for the underlying raw
    events).
    """

    @abstractmethod
    def save(self, projection: AgentTaskEventProjection) -> AgentTaskEventProjection:
        ...

    @abstractmethod
    def get(self, task_id: str) -> Optional[AgentTaskEventProjection]:
        ...
