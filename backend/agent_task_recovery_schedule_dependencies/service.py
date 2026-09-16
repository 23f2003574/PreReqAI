from datetime import datetime, timezone

from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_recovery_scheduling import LLMAgentTaskRecoveryPreflightSchedulingService

from .models import BLOCKED, FAILED, READY, UNKNOWN, AgentTaskRecoveryScheduleDependencyResult


class InvalidAgentTaskRecoveryScheduleDependencyError(ValueError):
    """Raised when check()/is_ready() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightScheduleDependencyService:
    """Prevents a Commit #1(-of-agent_task_recovery_scheduling) schedule
    from becoming dispatchable while task_id's own task-to-task
    dependencies remain unresolved -- never a second dependency system
    (Rule: "Do not create a second dependency system"): check()/
    is_ready() resolve task_id's dependency graph entirely through this
    repository's own existing infrastructure -- Commit #6(-of-
    agent_task_dependency_resolution)'s own LLMAgentTaskDependencyResolver.
    resolve() (transitive, preferred: distinguishes ready/pending/failed/
    blocked/unresolved/cyclic in one pass) when a dependency_resolver is
    supplied, falling back to Commit #5(-of-agent_task_dependencies)'s
    own LLMAgentTaskDependencyService.check_dependencies() (direct only)
    when only a dependency_service is given, and to "nothing outstanding"
    when neither is configured at all -- the exact same dual-collaborator,
    resolver-takes-priority shape backend.agent_task_readiness.
    LLMAgentTaskReadinessService._check_dependencies() already establishes
    for a comparable case, reused here rather than re-derived.

    Bound to the exact schedule/preflight (Rule): check() first looks
    task_id's exact schedule_id up through Commit #1(-of-
    agent_task_recovery_scheduling)'s own scheduling_service.get() --
    which already refuses to return a schedule recorded under a
    different task_id (the same "wrong task_id makes a schedule
    invisible" convention that service's own validation collaborator
    already relies on) -- and carries its recorded preflight_id straight
    through onto this result, never re-derived.

    Distinguishes ready/blocked/failed/unknown (Rule): see this
    package's own models.py docstring for the exact state vocabulary and
    priority order.

    Re-checks live (Rule: "Re-check current dependency state rather than
    trusting scheduling-time data"): every call to
    LLMAgentTaskDependencyResolver.resolve()/check_dependencies() reads
    the dependency graph's CURRENT state fresh -- nothing here is ever
    cached from scheduling time, nor from any earlier call to this
    service itself.

    Read-only (Rule: "Do not mutate task state or execute recovery"):
    check()/is_ready() only ever call get()/resolve()/check_dependencies()
    -- never transition(), schedule(), authorize(), or anything from
    backend.agent_task_recovery_guardrails'/agent_task_recovery_scheduling's
    own write paths.

    Deterministic and idempotent (Rule): a fixed dependency graph and
    schedule record always resolve to the exact same state/blockers,
    since every read here is itself already deterministic (Commit #6's
    own resolve() guarantees this) and nothing this class does has any
    side effect to make a repeated call diverge.
    """

    def __init__(
        self,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        dependency_resolver: LLMAgentTaskDependencyResolver = None,
        dependency_service: LLMAgentTaskDependencyService = None,
    ):
        """
        Args:
            scheduling_service: Defaults to a fresh
                backend.agent_task_recovery_scheduling.
                LLMAgentTaskRecoveryPreflightSchedulingService; pass the
                real instance holding a task's actual schedules for
                check() to ever find anything
            dependency_resolver: No default (mirrors
                LLMAgentTaskReadinessService's own dependency_resolver --
                it must be the exact instance built over a task's real
                dependency graph). Enables the *transitive*
                ready/pending/failed/blocked/unresolved/cycle check, and
                takes priority over dependency_service when both are
                given
            dependency_service: No default; enables only a *direct*-
                dependencies check (via check_dependencies()), and only
                when dependency_resolver is not also given. With
                neither collaborator supplied, every schedule's own
                dependency check reports READY -- there is no dependency
                infrastructure to consult
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._dependency_resolver = dependency_resolver
        self._dependency_service = dependency_service

    def is_ready(self, task_id: str, schedule_id: str) -> bool:
        """Shorthand for check(task_id, schedule_id).ready."""
        return self.check(task_id, schedule_id).ready

    def check(self, task_id: str, schedule_id: str) -> AgentTaskRecoveryScheduleDependencyResult:
        """Whether task_id's exact schedule_id is currently clear to
        dispatch, dependency-wise, right now.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyError: If task_id
                or schedule_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        now = datetime.now(timezone.utc)

        schedule = self._scheduling_service.get(task_id, schedule_id)
        if schedule is None:
            return AgentTaskRecoveryScheduleDependencyResult(
                task_id=task_id, schedule_id=schedule_id, preflight_id=None,
                ready=False, state=UNKNOWN,
                blockers=("no schedule is recorded for this task_id/schedule_id",),
                ready_dependencies=(), pending_dependencies=(), failed_dependencies=(),
                blocked_dependencies=(), unresolved_dependencies=(), cycles=(),
                checked_at=now,
            )

        (
            ready_deps, pending_deps, failed_deps, blocked_deps, unresolved_deps, cycles,
        ) = self._resolve(task_id)

        # ready_deps is the resolver's own "dependency frontier" bucket --
        # not yet COMPLETED, merely next in line to start (see
        # backend.agent_task_dependency_resolution.AgentTaskDependencyResolution's
        # own docstring, Rule 5: "the dependency frontier that must
        # complete before the task can proceed"). Recovery dispatch
        # requires every dependency actually COMPLETED, not merely
        # unblocked to start, so it is folded into the same "not
        # completed yet" blocker as pending_deps here -- unlike backend.
        # agent_task_readiness.LLMAgentTaskReadinessService's own
        # comparable check, which (for the different question of "may
        # task_id itself enter RUNNING") leaves ready_dependencies out of
        # its own blocking reasons entirely.
        not_yet_completed = pending_deps + ready_deps
        blockers = (
            [f"dependency {dep!r} failed or was cancelled" for dep in failed_deps]
            + [f"dependency graph contains a cycle involving {dep!r}" for dep in cycles]
            + [f"dependency {dep!r} could not be resolved (missing task)" for dep in unresolved_deps]
            + [f"dependency {dep!r} is blocked by an upstream failure/cycle" for dep in blocked_deps]
            + [f"dependency {dep!r} has not completed yet" for dep in not_yet_completed]
        )

        if failed_deps or cycles:
            state = FAILED
        elif unresolved_deps:
            state = UNKNOWN
        elif blocked_deps or not_yet_completed:
            state = BLOCKED
        else:
            state = READY

        return AgentTaskRecoveryScheduleDependencyResult(
            task_id=task_id, schedule_id=schedule_id, preflight_id=schedule.preflight_id,
            ready=not blockers, state=state, blockers=tuple(blockers),
            ready_dependencies=ready_deps, pending_dependencies=pending_deps,
            failed_dependencies=failed_deps, blocked_dependencies=blocked_deps,
            unresolved_dependencies=unresolved_deps, cycles=cycles,
            checked_at=now,
        )

    def _resolve(self, task_id: str) -> tuple:
        if self._dependency_resolver is not None:
            resolution = self._dependency_resolver.resolve(task_id)
            return (
                tuple(resolution.ready_dependencies),
                tuple(resolution.pending_dependencies),
                tuple(resolution.failed_dependencies),
                tuple(resolution.blocked_dependencies),
                tuple(resolution.unresolved_dependencies),
                tuple(resolution.cycles),
            )
        if self._dependency_service is not None:
            result = self._dependency_service.check_dependencies(task_id)
            return (), tuple(result.pending), tuple(result.failed), tuple(result.blocked), (), ()
        return (), (), (), (), (), ()

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleDependencyError(
                f"{field_name} is required and must be a non-empty string"
            )
