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
    """

    @abstractmethod
    def save(self, event: AgentTaskEvent) -> AgentTaskEvent:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...
