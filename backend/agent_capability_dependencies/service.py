from backend.agent_capability_registry import ACTIVE, LLMAgentCapabilityRegistry
from backend.agent_task_planning import cyclic_step_ids

from .in_memory_store import InMemoryDependencyStore
from .models import CapabilityDependency, DependencyCheckResult
from .store import DependencyStore


class InvalidDependencyError(ValueError):
    """Raised when a capability_id/dependency_id is missing or blank, or
    validate_dependencies() is given something other than a list of
    strings."""


class SelfDependencyError(InvalidDependencyError):
    """Raised when add_dependency() is given the same capability_id and
    dependency_id -- a capability cannot depend on itself."""


class DuplicateDependencyError(InvalidDependencyError):
    """Raised when add_dependency() is given a (capability_id,
    dependency_id) pair that is already recorded."""


class CyclicDependencyError(InvalidDependencyError):
    """Raised when add_dependency() would introduce a cycle into the
    dependency graph -- the edge is never recorded."""


class UnknownDependencyError(KeyError):
    """Raised when remove_dependency() is given a (capability_id,
    dependency_id) pair that is not currently recorded."""


class LLMAgentCapabilityDependencyService:
    """Tracks prerequisite relationships between Commit #1 registered
    capabilities, and checks whether a set of them is internally
    satisfiable.

    Not a generic graph framework: cycle detection is entirely
    backend.agent_task_planning.cyclic_step_ids, the exact same
    deterministic DFS-coloring cycle check backend.agent_plan_validation
    already reuses for an unrelated domain's own dependency graph (a
    plan's steps and their depends_on) -- reused here verbatim against
    capability_id/dependency_id edges instead of step_id/depends_on ones,
    never a second cycle-detection algorithm. Capability existence and
    "is this a valid prerequisite at all" both go straight through
    Commit #1's own LLMAgentCapabilityRegistry -- get()/exists() for
    existence, and status == ACTIVE for availability (Rule:
    "archived/unavailable dependencies are not valid prerequisites";
    Rule: "scope/availability checks should reuse existing capability
    resolution") -- never a second capability existence/availability
    check.

    add_dependency() keeps the graph acyclic by construction, the same
    reject-at-write-time discipline
    backend.notebook_dependencies.LLMNotebookDependencyService._check_acyclic()
    already applies to its own (unrelated) dependency graph: a proposed
    edge that would create a cycle is rejected outright, never stored.
    validate_dependencies() re-runs the same cycle check anyway (Rule:
    "detect dependency cycles deterministically" is a standing
    invariant, not just an add-time gate) -- this also protects a graph
    loaded from a JsonDependencyStore file that was edited outside this
    service, which add_dependency()'s own guard cannot see.

    add_dependency()/remove_dependency() only ever touch this service's
    own dependency-edge store; neither one calls
    LLMAgentCapabilityRegistry.update()/archive(), so Commit #1's own
    registry data is always exactly as it was before (Rule: "dependency
    operations must preserve existing registry data").
    """

    def __init__(self, capability_registry: LLMAgentCapabilityRegistry, store: DependencyStore = None):
        self._capability_registry = capability_registry
        self.store = store if store is not None else InMemoryDependencyStore()

    def add_dependency(self, capability_id: str, dependency_id: str) -> CapabilityDependency:
        """Record that capability_id depends on dependency_id.

        Raises:
            InvalidDependencyError: If capability_id or dependency_id is
                missing or blank
            SelfDependencyError: If capability_id equals dependency_id
            UnknownCapabilityError: If capability_id or dependency_id was
                never registered in the Commit #1 capability registry
            DuplicateDependencyError: If this exact edge is already
                recorded
            CyclicDependencyError: If adding this edge would create a
                dependency cycle
        """
        self._validate_id(capability_id, "capability_id")
        self._validate_id(dependency_id, "dependency_id")
        if capability_id == dependency_id:
            raise SelfDependencyError(f"capability {capability_id!r} cannot depend on itself")

        # Rule: "reject [dependencies] for unknown capabilities" -- both
        # ends of the edge must already be registered. Commit #1's own
        # UnknownCapabilityError propagates unchanged.
        self._capability_registry.get(capability_id)
        self._capability_registry.get(dependency_id)

        if self.store.get(capability_id, dependency_id) is not None:
            raise DuplicateDependencyError(
                f"dependency {capability_id!r} -> {dependency_id!r} is already recorded"
            )

        edges = self._edges_map()
        edges.setdefault(capability_id, []).append(dependency_id)
        nodes = sorted(set(edges) | {dep for deps in edges.values() for dep in deps})
        cyclic = cyclic_step_ids(nodes, edges)
        if capability_id in cyclic:
            raise CyclicDependencyError(
                f"adding dependency {capability_id!r} -> {dependency_id!r} would create a cycle"
            )

        return self.store.save(CapabilityDependency(capability_id=capability_id, dependency_id=dependency_id))

    def remove_dependency(self, capability_id: str, dependency_id: str) -> None:
        """Remove a previously recorded dependency edge.

        Raises:
            InvalidDependencyError: If capability_id or dependency_id is
                missing or blank
            UnknownDependencyError: If no such edge is recorded
        """
        self._validate_id(capability_id, "capability_id")
        self._validate_id(dependency_id, "dependency_id")

        if not self.store.remove(capability_id, dependency_id):
            raise UnknownDependencyError(f"no dependency {capability_id!r} -> {dependency_id!r} is recorded")

    def get_dependencies(self, capability_id: str, transitive: bool = False) -> list:
        """The capability_ids capability_id depends on -- direct only by
        default; every capability reachable by following dependency
        edges when transitive=True (capability_id itself never included).

        Raises:
            InvalidDependencyError: If capability_id is missing or blank
        """
        self._validate_id(capability_id, "capability_id")
        if not transitive:
            return [edge.dependency_id for edge in self.store.dependencies_of(capability_id)]
        return sorted(self._reachable(capability_id, self._edges_map()))

    def get_dependents(self, capability_id: str, transitive: bool = False) -> list:
        """The capability_ids that depend on capability_id -- direct only
        by default; every capability that transitively depends on it
        when transitive=True (capability_id itself never included).

        Raises:
            InvalidDependencyError: If capability_id is missing or blank
        """
        self._validate_id(capability_id, "capability_id")
        if not transitive:
            return [edge.capability_id for edge in self.store.dependents_of(capability_id)]
        return sorted(self._reachable(capability_id, self._reverse_edges_map()))

    def validate_dependencies(self, capability_ids: list) -> DependencyCheckResult:
        """Whether capability_ids, together with everything they
        transitively depend on, forms an internally satisfiable set:
        every referenced capability is registered, ACTIVE, and the whole
        induced subgraph is acyclic.

        Raises:
            InvalidDependencyError: If capability_ids is not a list of
                non-empty strings
        """
        if not isinstance(capability_ids, list) or not all(
            isinstance(item, str) and item for item in capability_ids
        ):
            raise InvalidDependencyError("capability_ids must be a list of non-empty strings")

        edges = self._edges_map()
        reachable = set(capability_ids)
        frontier = list(capability_ids)
        while frontier:
            node = frontier.pop()
            for dependency_id in edges.get(node, ()):
                if dependency_id not in reachable:
                    reachable.add(dependency_id)
                    frontier.append(dependency_id)

        missing = set()
        unavailable = set()
        for node in reachable:
            if not self._capability_registry.exists(node):
                missing.add(node)
            elif self._capability_registry.get(node).status != ACTIVE:
                unavailable.add(node)

        induced_edges = {node: [dep for dep in edges.get(node, ()) if dep in reachable] for node in reachable}
        cyclic = cyclic_step_ids(sorted(reachable), induced_edges)

        unresolved = {
            root
            for root in capability_ids
            if ({root} | self._reachable(root, edges)) & (missing | unavailable | cyclic)
        }

        return DependencyCheckResult(
            valid=not (missing or cyclic or unresolved),
            missing_capabilities=sorted(missing),
            cycles=sorted(cyclic),
            unresolved_dependencies=sorted(unresolved),
        )

    def _edges_map(self) -> dict:
        edges = {}
        for edge in self.store.all():
            edges.setdefault(edge.capability_id, []).append(edge.dependency_id)
        return edges

    def _reverse_edges_map(self) -> dict:
        edges = {}
        for edge in self.store.all():
            edges.setdefault(edge.dependency_id, []).append(edge.capability_id)
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
