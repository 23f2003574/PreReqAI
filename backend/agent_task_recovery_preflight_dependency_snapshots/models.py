from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

# One entry's effective dependency state, captured at snapshot time (or
# recomputed live for diff()'s own "current" side) -- deliberately a
# richer vocabulary than backend.agent_task_recovery_schedule_dependencies.
# models' own READY/BLOCKED/FAILED/UNKNOWN (that package's own state is a
# single, most-severe-wins verdict for a whole SCHEDULE; this one is a
# per-DEPENDENCY classification, so every one of
# backend.agent_task_dependency_resolution.AgentTaskDependencyResolution's
# own six buckets gets its own distinct value here, plus COMPLETED for a
# dependency present in the graph but in none of those six buckets --
# resolve()'s own "no bucket means satisfied" convention, made explicit
# rather than left as an absence, since a snapshot needs to be able to
# name a dependency as "already done" just as much as "still blocking").
READY = "ready"
PENDING = "pending"
FAILED = "failed"
BLOCKED = "blocked"
UNRESOLVED = "unresolved"
CYCLIC = "cyclic"
COMPLETED = "completed"
DEPENDENCY_SNAPSHOT_STATES = frozenset({READY, PENDING, FAILED, BLOCKED, UNRESOLVED, CYCLIC, COMPLETED})


@dataclass(frozen=True)
class AgentTaskDependencySnapshotEntry:
    """One dependency_task_id's effective state, as of one snapshot (or
    one live re-check) -- a plain value object, never itself mutated.
    """

    dependency_task_id: str
    state: str


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshot:
    """LLMAgentTaskRecoveryPreflightDependencySnapshotService.create()'s
    durable, point-in-time capture of task_id's whole dependency graph,
    bound to the EXACT preflight it was taken for -- never a second
    dependency graph engine (Rule: "Reuse existing dependency resolver;
    don't duplicate dependency semantics"): every entry in `dependencies`
    is read straight from backend.agent_task_dependency_resolution.
    LLMAgentTaskDependencyResolver.resolve() (or, as a fallback, backend.
    agent_task_dependencies.LLMAgentTaskDependencyService.
    check_dependencies()) -- this class never traverses an edge or
    classifies a lifecycle state itself.

    Bound to the exact (task_id, preflight_id) this snapshot was taken
    for (Rule: "capture ... for the exact task/preflight") -- preflight_id
    is verified, at create() time, to actually be a preflight recorded for
    task_id via backend.agent_task_recovery_guardrails' own
    LLMAgentTaskRecoveryPreflightStore, never merely trusted from the
    caller.

    `dependencies` holds one AgentTaskDependencySnapshotEntry per
    dependency_task_id reachable from task_id at capture time, sorted by
    dependency_task_id for deterministic comparison -- task_id itself is
    never included (the same "never includes itself" convention every
    dependency-graph result in this repository already uses).

    Immutable once recorded (Rule: "Preserve immutable snapshots") -- a
    frozen dataclass, never replaced or edited in place; the store this
    class is persisted through has no update()/delete() at all, only
    save()/get()/list_for_task(), the same append-only discipline this
    project's own comparable history stores already establish.
    """

    task_id: str
    preflight_id: str
    dependencies: tuple
    captured_at: datetime
    snapshot_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["captured_at"] = self.captured_at.isoformat()
        data["dependencies"] = [asdict(entry) for entry in self.dependencies]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryPreflightDependencySnapshot":
        payload = dict(data)
        value = payload.get("captured_at")
        if isinstance(value, str):
            payload["captured_at"] = datetime.fromisoformat(value)
        payload["dependencies"] = tuple(
            AgentTaskDependencySnapshotEntry(**entry) for entry in payload.get("dependencies") or ()
        )
        return cls(**payload)


@dataclass(frozen=True)
class AgentTaskDependencySnapshotStateChange:
    """One dependency_task_id whose own state moved between a snapshot
    and a later diff() call, without landing in either of diff()'s own
    more specific `resolved`/`newly_blocked` buckets (see
    AgentTaskRecoveryPreflightDependencySnapshotDiff's own docstring)."""

    dependency_task_id: str
    previous_state: str
    current_state: str


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotDiff:
    """LLMAgentTaskRecoveryPreflightDependencySnapshotService.diff()'s
    complete, read-only comparison of one persisted snapshot against
    task_id's CURRENT dependency graph -- never a second reconciliation
    engine (Rule: "reuse existing dependency resolver; don't duplicate
    dependency semantics") and never itself a scheduling/recovery
    decision (Rule: "Read-only diff(); no scheduling/recovery side
    effects"): every fact here comes from comparing the snapshot's own
    already-persisted entries against one fresh resolve()/
    check_dependencies() call, nothing more.

    Every dependency_task_id present on either side is classified into
    exactly one bucket, never more than one (Rule: "Detect added,
    removed, resolved, newly-blocked, and state-changed dependencies"):

        added: reachable now, but not part of the snapshot at all --
            a new dependency edge/node since the snapshot was taken.
        removed: part of the snapshot, but not reachable at all now --
            the dependency edge/node itself is gone (distinct from
            `resolved`, which stays reachable, just COMPLETED).
        resolved: reachable on both sides, and now COMPLETED when it
            was not COMPLETED in the snapshot.
        newly_blocked: reachable on both sides, now BLOCKED when it was
            not BLOCKED in the snapshot -- called out as its own bucket
            (rather than folded into state_changed) since a newly-BLOCKED
            dependency is the one transition callers most need to react
            to.
        state_changed: reachable on both sides, with any OTHER state
            change (e.g. ready->pending, pending->failed, blocked->
            pending) -- every transition not already covered by
            `resolved`/`newly_blocked` above, as
            AgentTaskDependencySnapshotStateChange entries.

    A dependency whose state is identical on both sides appears in none
    of the above (Rule: "identical graph" produces every bucket empty).
    changed is exactly whether any bucket above is non-empty.
    """

    task_id: str
    snapshot_id: str
    preflight_id: str
    added: tuple
    removed: tuple
    resolved: tuple
    newly_blocked: tuple
    state_changed: tuple
    changed: bool
    diffed_at: datetime
