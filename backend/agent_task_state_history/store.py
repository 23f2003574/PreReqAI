from abc import ABC, abstractmethod

from .models import TaskTransitionRecord


class AgentTaskTransitionStore(ABC):
    """Persistence for the append-only record of every Commit #1 AgentTask
    transition (including its own initial CREATED entry).

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
