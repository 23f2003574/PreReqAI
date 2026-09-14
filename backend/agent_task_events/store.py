from abc import ABC, abstractmethod

from .models import AgentTaskEvent


class AgentTaskEventStore(ABC):
    """Persistence for the append-only stream of every AgentTaskEvent
    emitted for a task.

    The same save()/list_for_task() split
    backend.agent_task_state_history.AgentTaskTransitionStore already uses
    for its own append-only trail. There is no update() or delete(): an
    event is never overwritten or removed once recorded (Rule: "Append-only
    event records").

    all() is an additive read path (Commit #2), added for the same reason
    backend.agent_task_dependencies.TaskDependencyStore.all() exists
    alongside its own get()/dependencies_of(): a cross-task query needs a
    "every record ever saved" read the same way a whole-graph operation
    does, and this is that store's own existing "list everything" naming
    convention, not a second store or a new query framework.
    """

    @abstractmethod
    def save(self, event: AgentTaskEvent) -> AgentTaskEvent:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...

    @abstractmethod
    def all(self) -> list:
        """Every event ever recorded, across every task, oldest to
        newest -- for cross-task queries only (see Commit #2's
        LLMAgentTaskEventQueryService); ordinary per-task reads still use
        list_for_task()."""
        ...
