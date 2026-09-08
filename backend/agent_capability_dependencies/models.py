from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class CapabilityDependency:
    """One directed edge in the capability dependency graph:
    capability_id depends on dependency_id -- dependency_id must be
    available for capability_id to be usable.

    An immutable value object, the same shape and discipline
    backend.notebook_dependencies.LLMNotebookDependency already uses for
    an unrelated domain's own dependency edges (source/target there,
    capability_id/dependency_id here to match this commit's own
    method signatures literally). LLMAgentCapabilityDependencyService
    never mutates one once recorded -- changing a dependency means
    remove_dependency() then add_dependency(), never an update.
    """

    capability_id: str
    dependency_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "CapabilityDependency":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)


@dataclass(frozen=True)
class DependencyCheckResult:
    """validate_dependencies()'s complete, structured outcome for one
    requested set of capability_ids -- never a bare True/False, so every
    reason a capability set isn't internally satisfiable is reported at
    once (Rule: "missing dependencies must be reported rather than
    silently ignored").

    missing_capabilities: capability_ids reachable from the requested
        set (the set itself, or anything they transitively depend on)
        that were never registered in the Commit #1 capability registry
        at all.
    cycles: capability_ids that participate in a dependency cycle within
        the subgraph reachable from the requested set.
    unresolved_dependencies: capability_ids from the requested set whose
        own (possibly transitive) dependency chain includes a missing,
        archived/unavailable, or cyclic capability -- i.e. a requested
        capability that cannot actually be satisfied, even though it may
        not itself be missing or cyclic.
    valid is exactly `not (missing_capabilities or cycles or
    unresolved_dependencies)`.
    """

    valid: bool
    missing_capabilities: list
    cycles: list
    unresolved_dependencies: list
