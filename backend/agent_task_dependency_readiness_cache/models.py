from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.agent_task_dependency_readiness_plan import AgentTaskDependencyReadinessPlan


@dataclass(frozen=True)
class AgentTaskDependencyReadinessCacheEntry:
    """One cached Commit #8 AgentTaskDependencyReadinessPlan for
    task_id, plus the fingerprint LLMAgentTaskDependencyReadinessCache
    itself needs to tell whether it is still valid.

    fingerprint maps every task_id the cached plan's own resolution
    actually touched (task_id itself, plus every node in plan's own
    execution_order) to that task's Commit #1 updated_at at the moment
    this entry was cached -- Rule: "cache entries should carry enough
    dependency/version information to detect staleness using existing
    repository mechanisms." updated_at is Commit #1's own, already-
    existing per-task version signal (bumped by every
    AgentTaskStore.save(), i.e. every real transition()); this is
    deliberately not a new versioning scheme invented for this cache.
    A node no longer resolvable via Commit #1 (defensive only -- see
    Commit #6's own unresolved_dependencies) fingerprints as None.
    """

    task_id: str
    plan: AgentTaskDependencyReadinessPlan
    fingerprint: dict
    cached_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
