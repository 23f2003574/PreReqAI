from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentTaskContext


class TaskContextStore(ABC):
    """Persistence operations for durable LLM agent task contexts.

    Mirrors backend.agent_policy_engine.LLMAgentPolicyStore's own
    save/get shape rather than introducing a second persistence
    abstraction. There is deliberately no delete() or list(): a task
    context is looked up only by its own task_id, which already binds it
    to one (agent_id, scope_id) pair.
    """

    @abstractmethod
    def save(self, task_context: LLMAgentTaskContext) -> LLMAgentTaskContext:
        ...

    @abstractmethod
    def get(self, task_id: str) -> Optional[LLMAgentTaskContext]:
        ...
