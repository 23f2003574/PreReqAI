from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_lifecycle import (
    CANCELLED,
    COMPLETED,
    FAILED,
    LLMAgentTaskLifecycleService,
    UnknownAgentTaskError,
)
from backend.agent_task_planning import cyclic_step_ids

from .models import AgentTaskDependencyResolution

_UNSATISFIABLE_STATES = frozenset({FAILED, CANCELLED})


class LLMAgentTaskDependencyResolver:
    """Resolves task_id's whole transitive Commit #5 dependency graph
    into one deterministic order plus a full lifecycle-state
    classification -- never a second dependency store or a second cycle
    detector.

    Every edge this class ever looks at comes from Commit #5's own
    LLMAgentTaskDependencyService.get_dependencies() (direct, per node)
    -- Rule: "reuse the existing dependency service/storage; do not
    invent another graph representation." Cycle detection is entirely
    backend.agent_task_planning.cyclic_step_ids, the exact same
    deterministic DFS-coloring check Commit #5 and backend.
    agent_capability_dependencies already reuse elsewhere in this
    repository, applied here to the same task_id/dependency_task_id
    edges Commit #5 itself defines -- never a third copy of cycle
    detection. Every dependency's lifecycle state comes straight from
    Commit #1's own LLMAgentTaskLifecycleService.get() -- resolve()
    never transitions anything, executes anything, or writes to the
    Commit #5 dependency store; it only ever reads (Rule: "read-only").

    blocked_dependencies mirrors backend.agent_capability_dependencies.
    DependencyCheckResult.unresolved_dependencies's own "a root whose own
    chain includes something broken" computation almost exactly (`{root
    for root in requested if (reachable(root) | {root}) &
    (missing | cyclic | unavailable)}`) -- renamed here because Commit
    #6's own result vocabulary already uses "unresolved" for a strictly
    narrower thing (a missing task reference), so the propagated-taint
    concept that module calls "unresolved" is spelled "blocked" here
    instead, to keep the two distinct rather than overloading one word
    for both.

    backend.agent_task_readiness.LLMAgentTaskReadinessService may be
    given this resolver directly (an optional dependency_resolver
    collaborator) instead of Commit #5's own bare
    LLMAgentTaskDependencyService, so readiness's own "dependencies"
    check can account for the *whole* transitive graph rather than only
    direct dependencies, without reimplementing any traversal of its own
    (Rule: "existing readiness checks should be able to consume this
    resolver rather than reimplement traversal").
    """

    def __init__(
        self,
        lifecycle_service: LLMAgentTaskLifecycleService,
        dependency_service: LLMAgentTaskDependencyService,
    ):
        self._lifecycle_service = lifecycle_service
        self._dependency_service = dependency_service

    def resolve(self, task_id: str) -> AgentTaskDependencyResolution:
        """Traverse task_id's full transitive dependency graph and
        classify every node in it.

        Raises:
            UnknownAgentTaskError: If task_id was never created via
                Commit #1
        """
        self._lifecycle_service.get(task_id)

        reachable = set(self._dependency_service.get_dependencies(task_id, transitive=True))
        edges = {node: self._dependency_service.get_dependencies(node) for node in reachable | {task_id}}

        nodes = sorted(reachable | {task_id})
        cyclic_nodes = set(cyclic_step_ids(nodes, edges))
        cycles = sorted(cyclic_nodes & (reachable | {task_id}))

        tasks_by_id = {}
        unresolved = set()
        for node in reachable:
            try:
                tasks_by_id[node] = self._lifecycle_service.get(node)
            except UnknownAgentTaskError:
                unresolved.add(node)

        cyclic_dependencies = reachable & cyclic_nodes
        failed = {
            node
            for node in reachable - unresolved - cyclic_dependencies
            if tasks_by_id[node].current_state in _UNSATISFIABLE_STATES
        }

        taint_sources = unresolved | cyclic_dependencies | failed
        blocked = set()
        for node in reachable - unresolved - cyclic_dependencies - failed:
            node_reachable = set(self._dependency_service.get_dependencies(node, transitive=True))
            if node_reachable & taint_sources:
                blocked.add(node)

        ready, pending = set(), set()
        for node in reachable - unresolved - cyclic_dependencies - failed - blocked:
            task = tasks_by_id[node]
            if task.current_state == COMPLETED:
                continue
            direct_deps = edges.get(node, [])
            if all(tasks_by_id[dep].current_state == COMPLETED for dep in direct_deps):
                ready.add(node)
            else:
                pending.add(node)

        orderable = reachable - unresolved - cyclic_dependencies
        ordered_dependencies = self._topological_order(orderable, edges)

        return AgentTaskDependencyResolution(
            task_id=task_id,
            ordered_dependencies=ordered_dependencies,
            ready_dependencies=sorted(ready),
            pending_dependencies=sorted(pending),
            failed_dependencies=sorted(failed),
            blocked_dependencies=sorted(blocked),
            unresolved_dependencies=sorted(unresolved),
            cycles=cycles,
        )

    @staticmethod
    def _topological_order(nodes: set, edges: dict) -> list:
        """nodes, in one deterministic order where every node's own
        direct dependencies (per edges, restricted to nodes) precede it
        -- Kahn's algorithm, breaking every tie alphabetically so the
        exact same graph always resolves to the exact same order (Rule:
        "deterministic ordering for identical graphs"), regardless of
        edge-insertion order in the underlying Commit #5 store.
        """
        remaining = {node: sorted(dep for dep in edges.get(node, []) if dep in nodes) for node in nodes}
        ordered = []
        while remaining:
            frontier = sorted(node for node, deps in remaining.items() if not deps)
            if not frontier:
                break  # unreachable: `nodes` already excludes every cyclic node
            for node in frontier:
                ordered.append(node)
                del remaining[node]
            for deps in remaining.values():
                deps[:] = [dep for dep in deps if dep not in frontier]
        return ordered
