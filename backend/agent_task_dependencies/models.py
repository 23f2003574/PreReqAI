from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class TaskDependency:
    """One directed edge in the task dependency graph: task_id depends
    on dependency_task_id -- dependency_task_id must reach COMPLETED for
    task_id to be considered dependency-satisfied.

    An immutable value object, the same shape and discipline
    backend.agent_capability_dependencies.CapabilityDependency already
    uses for an unrelated domain's own dependency edges (capability_id/
    dependency_id there, task_id/dependency_task_id here to match this
    commit's own method signatures literally). LLMAgentTaskDependencyService
    never mutates one once recorded -- changing a dependency means
    remove_dependency() then add_dependency(), never an update.
    """

    task_id: str
    dependency_task_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "TaskDependency":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)


@dataclass(frozen=True)
class AgentTaskDependencyResult:
    """check_dependencies()'s complete, structured outcome for one
    task_id -- never a bare True/False, so every dependency_task_id
    standing between task_id and readiness is reported at once, not
    just whether *some* dependency is unsatisfied.

    dependencies: every task_id task_id directly depends on (Commit #1
        AgentTask.task_id values), in the exact order
        get_dependencies(task_id) already returns -- included here so a
        caller (see backend.agent_task_readiness.
        LLMAgentTaskReadinessService) never has to call
        get_dependencies() a second time just to explain this result.
    pending: dependencies not yet Commit #1 COMPLETED -- created,
        planned, ready, running, or paused; may still become satisfied.
    failed: dependencies Commit #1 FAILED or CANCELLED -- terminal, and
        can now never become satisfied by that dependency actually
        finishing.
    blocked: dependencies that are structurally unsatisfiable rather
        than merely unfinished -- the referenced task_id was never
        created at all, or task_id's own dependency edges participate
        in a cycle (defensive: add_dependency() already keeps the graph
        acyclic by construction, so this only ever fires against a
        store an external process edited directly -- see
        LLMAgentTaskDependencyService's own docstring).
    satisfied is exactly `not (pending or failed or blocked)` -- True
    for a task_id with no dependencies at all, the same "trivially
    satisfied when there is nothing to satisfy" convention
    backend.agent_capability_dependencies.DependencyCheckResult already
    uses for a requested set with no edges.
    """

    task_id: str
    satisfied: bool
    dependencies: list
    pending: list
    failed: list
    blocked: list
