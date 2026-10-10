from abc import ABC, abstractmethod
from typing import Optional

from .models import AgentTask


class AgentTaskStore(ABC):
    """Persistence operations for durable AgentTask lifecycle records.

    Mirrors backend.agent_task_context.TaskContextStore's own save/get
    shape rather than introducing a second persistence abstraction. There
    is deliberately no delete(): a task is retired by transitioning it
    into a terminal state (see models.TERMINAL_STATES), never removed.
    """

    @abstractmethod
    def save(self, task: AgentTask) -> AgentTask:
        ...

    @abstractmethod
    def get(self, task_id: str) -> Optional[AgentTask]:
        ...
