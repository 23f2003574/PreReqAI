from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# This commit's own effective-dependency-state vocabulary for one
# Commit #1(-of-this-series) scheduled preflight -- deliberately
# distinct from backend.agent_task_lifecycle's own AgentTask STATES
# (this describes the *dependency graph's* standing relative to a
# schedule, never the scheduled task's own lifecycle state) and from
# backend.agent_task_recovery_scheduling's own SCHEDULE_STATUSES (that
# describes the *schedule record's* own status -- scheduled/cancelled/
# invalidated -- a completely different axis from whether its
# dependencies happen to be satisfied right now).
READY = "ready"
BLOCKED = "blocked"
FAILED = "failed"
UNKNOWN = "unknown"
DEPENDENCY_STATES = frozenset({READY, BLOCKED, FAILED, UNKNOWN})


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleDependencyResult:
    """LLMAgentTaskRecoveryPreflightScheduleDependencyService.check()'s
    complete, structured verdict on whether task_id's exact schedule_id
    is currently clear to dispatch, dependency-wise -- never a bare
    True/False, so every blocker is reported at once (the same "collect
    everything" discipline backend.agent_task_readiness.
    AgentTaskReadinessResult and backend.agent_task_dependency_resolution.
    AgentTaskDependencyResolution already establish for a comparable
    case).

    Bound to the exact (task_id, schedule_id) this check() call named
    (Rule: "Bind the result to the exact schedule/preflight") --
    preflight_id is the schedule's own recorded preflight_id, read
    straight from Commit #1(-of-agent_task_recovery_scheduling)'s own
    scheduling_service.get(), never re-derived; it is None only when
    schedule_id itself does not exist for task_id at all (or belongs to
    a different task_id -- the same "wrong task_id makes a schedule
    invisible" convention backend.agent_task_recovery_scheduling.
    LLMAgentTaskRecoveryPreflightScheduleValidationService.validate()
    already uses for a comparable case).

    ready is exactly `not blockers`. state is the single, most-severe
    applicable AgentTaskRecoveryScheduleDependencyResult vocabulary
    word, in this fixed priority order (most severe first): FAILED (a
    dependency terminally failed/cancelled, or the graph is cyclic --
    can now never resolve on its own) outranks UNKNOWN (a referenced
    dependency task does not exist at all -- a structural gap, not
    merely unfinished work) outranks BLOCKED (still waiting: a pending
    dependency, one still at the front of the dependency frontier but
    not yet itself COMPLETED, or one transitively tainted by another
    node's own failure/cycle) outranks READY (nothing outstanding at
    all, or no schedule/dependency infrastructure was even configured
    to check against).

    ready_dependencies/pending_dependencies/failed_dependencies/
    blocked_dependencies/unresolved_dependencies/cycles are the exact
    same partition backend.agent_task_dependency_resolution.
    AgentTaskDependencyResolution.resolve() already returns for task_id
    -- carried through here unchanged as this result's own dependency
    evidence, though ready_dependencies (the resolver's own "next to
    start, not yet COMPLETED" frontier bucket) is folded into blockers
    right alongside pending_dependencies here: recovery dispatch needs
    every dependency actually COMPLETED, not merely unblocked to begin
    running (Rule: "Return blockers and dependency evidence for
    diagnostics/audit"), never re-derived a second way.
    """

    task_id: str
    schedule_id: str
    preflight_id: Optional[str]
    ready: bool
    state: str
    blockers: tuple
    ready_dependencies: tuple
    pending_dependencies: tuple
    failed_dependencies: tuple
    blocked_dependencies: tuple
    unresolved_dependencies: tuple
    cycles: tuple
    checked_at: datetime
