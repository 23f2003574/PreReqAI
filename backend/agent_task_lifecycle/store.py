from abc import ABC, abstractmethod
from typing import Optional

from .models import AgentTask, TaskTransitionRecord


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


class AgentTaskTransitionStore(ABC):
    """Persistence for the append-only record of every successful
    LLMAgentTaskLifecycleService.transition() call (including create()'s
    own initial CREATED entry).

    The same save()/list_for_-- split
    backend.agent_policy_templates.LLMAgentPolicyTemplateInstantiationStore
    already uses for its own append-only trail. There is no update() or
    delete(): a transition record is never overwritten or removed once
    recorded.
    """

    @abstractmethod
    def save(self, record: TaskTransitionRecord) -> TaskTransitionRecord:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...
