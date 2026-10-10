from backend.agent_task_lifecycle import (
    CANCELLED,
    COMPLETED,
    FAILED,
    LLMAgentTaskLifecycleService,
    UnknownAgentTaskError,
)
from backend.agent_task_planning import cyclic_step_ids

from .in_memory_store import InMemoryTaskDependencyStore
from .models import AgentTaskDependencyResult, TaskDependency
from .store import TaskDependencyStore

# Commit #1 states a dependency can settle into, from check_dependencies()'s
# own point of view -- FAILED and CANCELLED are grouped together because
# both mean the same thing to a task waiting on them: this prerequisite ran
# and will never reach COMPLETED, no different in effect from the
# dependent's own perspective. Every other Commit #1 state (created,
# planned, ready, running, paused) is still open-ended -- "pending" by
# elimination, not by a second enumerated list that could drift out of
# sync with Commit #1's own STATES.
_UNSATISFIABLE_STATES = frozenset({FAILED, CANCELLED})


class InvalidDependencyError(ValueError):
    """Raised when a task_id/dependency_task_id is missing or blank."""


class SelfDependencyError(InvalidDependencyError):
    """Raised when add_dependency() is given the same task_id and
    dependency_task_id -- a task cannot depend on itself."""


class DuplicateDependencyError(InvalidDependencyError):
    """Raised when add_dependency() is given a (task_id,
    dependency_task_id) pair that is already recorded."""


class CyclicDependencyError(InvalidDependencyError):
    """Raised when add_dependency() would introduce a cycle into the
    dependency graph -- the edge is never recorded."""


class UnknownDependencyError(KeyError):
    """Raised when remove_dependency() is given a (task_id,
    dependency_task_id) pair that is not currently recorded."""


class LLMAgentTaskDependencyService:
    """Tracks explicit prerequisite relationships between Commit #1
    AgentTasks, and checks whether a task_id's own dependencies are
    currently satisfied.

    Not a second generic dependency engine: cycle detection is entirely
    backend.agent_task_planning.cyclic_step_ids, the exact same
    deterministic DFS-coloring cycle check backend.
    agent_capability_dependencies.LLMAgentCapabilityDependencyService
    already reuses (itself reused from backend.agent_plan_validation) --
    applied here to task_id/dependency_task_id edges instead of
    capability_id/dependency_id or step_id/depends_on ones, never a
    third copy of cycle detection. Task existence goes straight through
    Commit #1's own LLMAgentTaskLifecycleService.get() -- its own
    UnknownAgentTaskError propagates unchanged for a missing task_id on
    either end of an edge, never a second "unknown task" error.

    add_dependency() keeps the graph acyclic by construction, the same
    reject-at-write-time discipline
    LLMAgentCapabilityDependencyService.add_dependency() already applies
    to its own (unrelated) dependency graph: a proposed edge that would
    create a cycle is rejected outright, never stored. check_dependencies()
    re-runs the same cycle check anyway -- this also protects a graph
    loaded from a JsonTaskDependencyStore file that was edited outside
    this service, which add_dependency()'s own guard cannot see.

    check_dependencies() only ever reads: Commit #1's own get() for every
    dependency's current_state, never transition(). Nothing here ever
    calls transition() itself, executes a task, or schedules one -- Rule:
    "do not execute dependent tasks" / "do not automatically change
    lifecycle state" hold by construction, since this service holds no
    reference to anything that could do either. backend.agent_task_readiness.
    LLMAgentTaskReadinessService consumes check_dependencies()'s own
    AgentTaskDependencyResult directly (an optional, injected
    dependency_service) rather than duplicating any of this -- Rule:
    "existing task readiness should be able to consume this result
    rather than duplicate dependency checks."
    """

    def __init__(self, lifecycle_service: LLMAgentTaskLifecycleService, store: TaskDependencyStore = None):
        self._lifecycle_service = lifecycle_service
        self.store = store if store is not None else InMemoryTaskDependencyStore()

    def add_dependency(self, task_id: str, dependency_task_id: str) -> TaskDependency:
        """Record that task_id depends on dependency_task_id.

        Raises:
            InvalidDependencyError: If task_id or dependency_task_id is
                missing or blank
            SelfDependencyError: If task_id equals dependency_task_id
            UnknownAgentTaskError: If task_id or dependency_task_id was
                never created via Commit #1
            DuplicateDependencyError: If this exact edge is already
                recorded
            CyclicDependencyError: If adding this edge would create a
                dependency cycle
        """
        self._validate_id(task_id, "task_id")
        self._validate_id(dependency_task_id, "dependency_task_id")
        if task_id == dependency_task_id:
            raise SelfDependencyError(f"task {task_id!r} cannot depend on itself")

        # Rule: "validate ... missing tasks" -- both ends of the edge
        # must already exist. Commit #1's own UnknownAgentTaskError
        # propagates unchanged.
        self._lifecycle_service.get(task_id)
        self._lifecycle_service.get(dependency_task_id)

        if self.store.get(task_id, dependency_task_id) is not None:
            raise DuplicateDependencyError(
                f"dependency {task_id!r} -> {dependency_task_id!r} is already recorded"
            )

        edges = self._edges_map()
        edges.setdefault(task_id, []).append(dependency_task_id)
        nodes = sorted(set(edges) | {dep for deps in edges.values() for dep in deps})
        cyclic = cyclic_step_ids(nodes, edges)
        if task_id in cyclic:
            raise CyclicDependencyError(
                f"adding dependency {task_id!r} -> {dependency_task_id!r} would create a cycle"
            )

        return self.store.save(TaskDependency(task_id=task_id, dependency_task_id=dependency_task_id))

    def remove_dependency(self, task_id: str, dependency_task_id: str) -> None:
        """Remove a previously recorded dependency edge.

        Raises:
            InvalidDependencyError: If task_id or dependency_task_id is
                missing or blank
            UnknownDependencyError: If no such edge is recorded
        """
        self._validate_id(task_id, "task_id")
        self._validate_id(dependency_task_id, "dependency_task_id")

        if not self.store.remove(task_id, dependency_task_id):
            raise UnknownDependencyError(f"no dependency {task_id!r} -> {dependency_task_id!r} is recorded")

    def get_dependencies(self, task_id: str, transitive: bool = False) -> list:
        """The task_ids task_id depends on -- direct only by default;
        every task reachable by following dependency edges when
        transitive=True (task_id itself never included).

        Raises:
            InvalidDependencyError: If task_id is missing or blank
        """
        self._validate_id(task_id, "task_id")
        if not transitive:
            return [edge.dependency_task_id for edge in self.store.dependencies_of(task_id)]
        return sorted(self._reachable(task_id, self._edges_map()))

    def get_dependents(self, task_id: str, transitive: bool = False) -> list:
        """The task_ids that depend on task_id -- direct only by
        default; every task that transitively depends on it when
        transitive=True (task_id itself never included).

        Raises:
            InvalidDependencyError: If task_id is missing or blank
        """
        self._validate_id(task_id, "task_id")
        if not transitive:
            return [edge.task_id for edge in self.store.dependents_of(task_id)]
        return sorted(self._reachable(task_id, self._reverse_edges_map()))

    def check_dependencies(self, task_id: str) -> AgentTaskDependencyResult:
        """Whether task_id's own direct dependencies are all currently
        Commit #1 COMPLETED.

        dependencies is task_id's direct dependency list (the same list
        get_dependencies(task_id) returns); pending/failed/blocked
        partition it three ways (see AgentTaskDependencyResult's own
        docstring). satisfied is exactly `not (pending or failed or
        blocked)` -- vacuously True for a task_id with no dependencies.

        Raises:
            UnknownAgentTaskError: If task_id was never created via
                Commit #1
        """
        self._lifecycle_service.get(task_id)

        dependencies = self.get_dependencies(task_id)

        edges = self._edges_map()
        nodes = sorted(set(edges) | {dep for deps in edges.values() for dep in deps} | {task_id})
        cyclic = cyclic_step_ids(nodes, edges)

        pending, failed, blocked = [], [], []
        if task_id in cyclic:
            # Defensive only -- add_dependency() never lets this happen
            # through this service's own API (see this class's own
            # docstring); only reachable against an externally-edited store.
            blocked = list(dependencies)
        else:
            for dependency_task_id in dependencies:
                try:
                    dependency_task = self._lifecycle_service.get(dependency_task_id)
                except UnknownAgentTaskError:
                    blocked.append(dependency_task_id)
                    continue

                if dependency_task.current_state == COMPLETED:
                    continue
                if dependency_task.current_state in _UNSATISFIABLE_STATES:
                    failed.append(dependency_task_id)
                else:
                    pending.append(dependency_task_id)

        return AgentTaskDependencyResult(
            task_id=task_id,
            satisfied=not (pending or failed or blocked),
            dependencies=dependencies,
            pending=pending,
            failed=failed,
            blocked=blocked,
        )

    def _edges_map(self) -> dict:
        edges = {}
        for edge in self.store.all():
            edges.setdefault(edge.task_id, []).append(edge.dependency_task_id)
        return edges

    def _reverse_edges_map(self) -> dict:
        edges = {}
        for edge in self.store.all():
            edges.setdefault(edge.dependency_task_id, []).append(edge.task_id)
        return edges

    @staticmethod
    def _reachable(start: str, edges: dict) -> set:
        """Every node reachable from start by following edges, excluding
        start itself -- a plain BFS over whatever direction edges
        encodes (forward for dependencies, reversed for dependents)."""
        found = set()
        frontier = [start]
        while frontier:
            node = frontier.pop()
            for neighbor in edges.get(node, ()):
                if neighbor not in found:
                    found.add(neighbor)
                    frontier.append(neighbor)
        return found

    @staticmethod
    def _validate_id(value, field_name):
        if not value or not isinstance(value, str):
            raise InvalidDependencyError(f"{field_name} is required and must be a non-empty string")
