from abc import ABC, abstractmethod

from .models import AgentTaskEvent


class AgentTaskEventStore(ABC):
    """Persistence for the append-only stream of every AgentTaskEvent
    emitted for a task.

    The same save()/list_for_task() split
    backend.agent_task_state_history.AgentTaskTransitionStore already uses
    for its own append-only trail. There is no update(): an event's own
    fields are never overwritten once recorded (Rule: "Append-only event
    records").

    all() is an additive read path (Commit #2), added for the same reason
    backend.agent_task_dependencies.TaskDependencyStore.all() exists
    alongside its own get()/dependencies_of(): a cross-task query needs a
    "every record ever saved" read the same way a whole-graph operation
    does, and this is that store's own existing "list everything" naming
    convention, not a second store or a new query framework.

    delete() is an additive Commit #9 extension, narrowly for retention/
    cleanup (Rule: "Reuse existing storage APIs" -- extend this store's own
    save()/list_for_task()/all() shape rather than building a second event
    store with its own deletion path). This does not weaken "append-only"
    for ordinary use: nothing in Commits #1-#8 ever calls delete(), and it
    exists solely for backend.agent_task_events.retention.
    LLMAgentTaskEventRetentionService.execute() to bound an otherwise
    unbounded log -- the same distinction this repository's own
    backend.session.execution_artifact_retention_service already draws
    between an entity's own immutability guarantee and a separate,
    explicitly-gated retention/GC concern over its history.
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

    @abstractmethod
    def delete(self, task_id: str, event_id: str) -> bool:
        """Remove one event if present. Returns whether it was present
        (Rule: "execute() must be idempotent" -- a second delete() of the
        same event_id is always a safe no-op, reported as False, never an
        error)."""
        ...
