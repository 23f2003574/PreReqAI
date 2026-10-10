from dataclasses import replace

from backend.agent_task_dependencies import TaskDependency, TaskDependencyStore


class StateOverrideLifecycleView:
    """A read-only stand-in for Commit #1's own
    LLMAgentTaskLifecycleService, used only to feed Commit #6's resolver
    a hypothetical snapshot: get(override_task_id) returns a copy of the
    real AgentTask with current_state replaced by override_state; every
    other task_id delegates to the real service completely unchanged
    (including raising its own UnknownAgentTaskError).

    Duck-typed rather than a subclass: Commit #6's resolver only ever
    calls .get(task_id) on whatever lifecycle_service it is given (see
    that module's own resolver.py), so this is all a "lifecycle_service"
    needs to provide here. Never transitions, creates, or otherwise
    writes anything -- there is no transition()/create() on this class
    at all, so it cannot be mistaken for a real, mutating service (Rule:
    "analysis only; do not perform the mutation ... itself").
    """

    def __init__(self, lifecycle_service, override_task_id: str, override_state: str):
        self._lifecycle_service = lifecycle_service
        self._override_task_id = override_task_id
        self._override_state = override_state

    def get(self, task_id: str):
        task = self._lifecycle_service.get(task_id)
        if task_id == self._override_task_id:
            task = replace(task, current_state=self._override_state)
        return task


class EdgeOverrideDependencyStore(TaskDependencyStore):
    """A read-only Commit #5 TaskDependencyStore view with at most one
    edge added or removed relative to the real store -- used only to
    build a temporary LLMAgentTaskDependencyService for Commit #6's
    resolver to read a hypothetical dependency graph through, never to
    persist anything for real.

    save()/remove() both raise: nothing durable is ever supposed to go
    through this view (Rule: "do not perform the mutation ... itself");
    every real write still goes through Commit #5's own store,
    completely untouched by this class.
    """

    def __init__(self, real_store: TaskDependencyStore, add_edge: TaskDependency = None, remove_edge: tuple = None):
        self._real_store = real_store
        self._add_edge = add_edge
        self._remove_edge = remove_edge

    def all(self) -> list:
        edges = [
            edge
            for edge in self._real_store.all()
            if self._remove_edge is None or (edge.task_id, edge.dependency_task_id) != self._remove_edge
        ]
        if self._add_edge is not None:
            edges = [
                edge
                for edge in edges
                if (edge.task_id, edge.dependency_task_id)
                != (self._add_edge.task_id, self._add_edge.dependency_task_id)
            ]
            edges.append(self._add_edge)
        return edges

    def dependencies_of(self, task_id: str) -> list:
        return [edge for edge in self.all() if edge.task_id == task_id]

    def dependents_of(self, task_id: str) -> list:
        return [edge for edge in self.all() if edge.dependency_task_id == task_id]

    def get(self, task_id: str, dependency_task_id: str):
        for edge in self.all():
            if edge.task_id == task_id and edge.dependency_task_id == dependency_task_id:
                return edge
        return None

    def save(self, dependency: TaskDependency) -> TaskDependency:
        raise NotImplementedError("EdgeOverrideDependencyStore is a read-only simulation view")

    def remove(self, task_id: str, dependency_task_id: str) -> bool:
        raise NotImplementedError("EdgeOverrideDependencyStore is a read-only simulation view")
