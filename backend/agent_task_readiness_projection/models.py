from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


@dataclass(frozen=True)
class AgentTaskReadinessProjection:
    """The latest known, persisted snapshot of one task_id's Commit #8
    readiness -- a derived read model built for cheap, repeated
    querying, never a second source of truth (Rule: "task lifecycle/
    dependency state remains authoritative"; Rule: "projection is
    derived state").

    Exactly one of these exists per task_id at a time (Behavior 3:
    "replace older projection for the same task"): LLMAgentTaskReadinessProjectionService.
    project() always overwrites, via save(), whatever was there before
    -- this is deliberately not an append-only history (unlike Commit
    #2's own TaskTransitionRecord), since "the latest known readiness"
    has no use for every stale intermediate value.

    ready/blocking_reasons/pending_dependencies/failed_dependencies are
    read straight off whatever Commit #8 AgentTaskDependencyReadinessPlan
    project() was given -- pending_dependencies is that plan's own
    pending_tasks, failed_dependencies is its own failed_tasks,
    blocking_reasons is one human-readable string per entry across
    pending_tasks/blocking_tasks/failed_tasks/unresolved_tasks (empty
    when ready is True) -- the same reason-string convention backend.
    agent_task_readiness.LLMAgentTaskReadinessService and backend.
    agent_task_dependency_change_impact already use elsewhere in this
    series, reused here rather than reinvented.

    source_version is task_id's own Commit #1 AgentTask.updated_at at
    the moment this projection was taken -- the same already-existing
    per-task version signal Commit #9's own cache fingerprint already
    reuses (Rule: "preserve enough source/version metadata to determine
    whether the projection is stale"; "reuse ... version information
    where already supported"). get() compares this against task_id's
    *current* updated_at to decide staleness (Rule: "never silently
    return a stale projection when existing version metadata can detect
    it") -- deliberately narrower than Commit #9's own cache fingerprint,
    which additionally checks every node in the whole resolved graph:
    doing that same full-graph check again here would make this class a
    second cache in every way that matters (Rule: "do not create
    another cache"), not a queryable projection of one already computed
    elsewhere. A caller that needs full-graph staleness protection
    already has it, for free, via Commit #9's own cache.get() -- this
    projection's own job is narrower: faithfully answer "is this exact
    snapshot still attached to the task_id it was taken for," nothing
    more.
    """

    task_id: str
    ready: bool
    blocking_reasons: list
    pending_dependencies: list
    failed_dependencies: list
    source_version: Optional[datetime]
    projection_id: str = field(default_factory=lambda: str(uuid4()))
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["evaluated_at"] = self.evaluated_at.isoformat()
        if isinstance(self.source_version, datetime):
            data["source_version"] = self.source_version.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskReadinessProjection":
        payload = dict(data)
        value = payload.get("evaluated_at")
        if isinstance(value, str):
            payload["evaluated_at"] = datetime.fromisoformat(value)
        source_version = payload.get("source_version")
        if isinstance(source_version, str):
            try:
                payload["source_version"] = datetime.fromisoformat(source_version)
            except ValueError:
                pass
        return cls(**payload)
