from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .dispatch import LLMAgentTaskRecoveryPreflightScheduleDispatchService
from .expiration import EXPIRED, LLMAgentTaskRecoveryPreflightScheduleExpirationService
from .models import CANCELLED, INVALIDATED
from .recovery import (
    BLOCKED as RECOVERY_BLOCKED,
    COMPLETE_HANDOFF,
    REDISPATCH,
    LLMAgentTaskRecoveryPreflightScheduleRecoveryService,
)
from .service import LLMAgentTaskRecoveryPreflightSchedulingService

# Deliberately NOT the same identifiers as backend.agent_policy_deployment_
# health's own HEALTHY/DEGRADED/UNHEALTHY/UNKNOWN vocabulary (the closest
# existing health-assessment precedent in this repository, whose own
# "worst signal wins" aggregation this module still reuses) -- the goal
# here names exactly "healthy, degraded, blocked" instead, and "blocked"
# as a bare name would collide with this same package's own Commit #9
# recovery.BLOCKED, so it is named HEALTH_BLOCKED while its actual string
# VALUE is still literally "blocked".
HEALTHY = "healthy"
DEGRADED = "degraded"
HEALTH_BLOCKED = "blocked"
HEALTH_STATUSES = frozenset({HEALTHY, DEGRADED, HEALTH_BLOCKED})

_SEVERITY_ORDER = (HEALTH_BLOCKED, DEGRADED, HEALTHY)


def _overall(severities: set) -> str:
    for status in _SEVERITY_ORDER:
        if status in severities:
            return status
    return HEALTHY


class InvalidAgentTaskRecoveryScheduleHealthError(ValueError):
    """Raised when assess()/summary() is given invalid arguments, or
    schedule_id names no recorded schedule for task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleHealthIssue:
    """One concrete, evidenced health problem -- never a synthesized or
    predicted one (Rule: "Do not treat historical failures as current
    failures unless repository state supports that conclusion"): every
    issue is produced by reading exactly one existing service's own
    current, live verdict for schedule_id, never by remembering that a
    check once failed."""

    code: str
    severity: str
    schedule_id: str
    reason: str
    evidence: tuple


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleHealthResult:
    """assess()'s complete, read-only, deterministic verdict. `status` is
    the single worst `issues[*].severity` present, or HEALTHY when
    `issues` is empty."""

    task_id: str
    schedule_id: Optional[str]
    status: str
    issues: tuple
    assessed_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleHealthSummary:
    """summary()'s task-wide rollup -- exactly `assess(task_id)` (every
    schedule, unscoped) plus a couple of counts a caller would otherwise
    have to derive itself."""

    task_id: str
    status: str
    schedule_count: int
    issue_count: int
    issues: tuple
    assessed_at: datetime


class LLMAgentTaskRecoveryPreflightScheduleHealthService:
    """Read-only health assessment for the recovery-preflight scheduling
    pipeline -- never a second metrics/observability system (Rule: "Do
    not introduce a second metrics/observability system"; "Do not invent
    monitoring infrastructure"): every signal this class reports is read
    straight from an existing service's own already-established, live
    verdict -- Commit #1's own effective status (INVALIDATED), Commit
    #8's own expiration `check()`, Commit #9's own recovery
    `plan_recovery()` (orphaned/interrupted dispatch, and its own
    ambiguous-dispatch-history BLOCKED case for "inconsistent schedule
    state"), Commit #6's own capacity `check()`, and Commit #7's own
    backoff `calculate()` (repeated rescheduling, retry exhaustion) --
    nothing here recomputes any of those checks itself.

    One exception, and why it cannot be otherwise: "duplicate active
    schedule for the same preflight_id" is Commit #4's own reconciliation
    detection, but Commit #4's only public entry points
    (`reconcile()`/`reconcile_all()`) always ALSO cancel what they find --
    calling either one from a read-only assess() would itself violate
    Rule 1 ("Read-only; never modify or execute recovery"). This class
    therefore reimplements only that one detection rule (never the write)
    read-only, over Commit #1's own already-read-only `list()` -- the
    exact same "keep earliest SCHEDULED per preflight_id, flag the rest"
    algorithm Commit #4's own `_run()` already uses, kept in lockstep with
    it rather than duplicated logic drifting apart over time.

    A cleanly CANCELLED schedule is never itself reported unhealthy (Rule:
    "Do not treat historical failures as current failures unless
    repository state supports that conclusion") -- it is resolved, not a
    live problem; every other check below is simply skipped for it.

    A single schedule can carry more than one simultaneous issue (e.g.
    invalidated AND capacity-blocked for the same underlying authorization
    problem) -- assess() never early-exits after the first one found, and
    `status` is the single worst severity across every issue found, for
    every schedule assessed, the same "worst signal wins" aggregation
    backend.agent_policy_deployment_health's own HealthResult already
    establishes for a comparable case.

    Deterministic for a fixed `now` (Rule): every underlying check this
    class calls is itself already deterministic for a fixed `now` (or,
    for capacity, time-independent), and this class performs no write of
    its own between them.
    """

    def __init__(
        self,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        dispatch_service: LLMAgentTaskRecoveryPreflightScheduleDispatchService = None,
        recovery_service: LLMAgentTaskRecoveryPreflightScheduleRecoveryService = None,
        expiration_service: LLMAgentTaskRecoveryPreflightScheduleExpirationService = None,
        capacity_service=None,
        backoff_service=None,
    ):
        """
        Args:
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService.
            dispatch_service: Defaults to a fresh Commit #3 service built
                over scheduling_service.
            recovery_service: Defaults to a fresh Commit #9 service built
                over scheduling_service/dispatch_service -- reused for
                its own orphan/interrupted-dispatch/ambiguous-state
                detection.
            expiration_service: Optional Commit #8 service -- when
                omitted, expiration is simply not assessed (Rule:
                "assess signals already available in the repository";
                none is fabricated for a signal that was never wired).
            capacity_service: Optional Commit #6
                LLMAgentTaskRecoveryPreflightScheduleCapacityService.
            backoff_service: Optional Commit #7
                LLMAgentTaskRecoveryPreflightScheduleBackoffService.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._dispatch_service = (
            dispatch_service
            if dispatch_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDispatchService(scheduling_service=self._scheduling_service)
        )
        self._recovery_service = (
            recovery_service
            if recovery_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleRecoveryService(
                scheduling_service=self._scheduling_service, dispatch_service=self._dispatch_service,
                expiration_service=expiration_service,
            )
        )
        self._expiration_service = expiration_service
        self._capacity_service = capacity_service
        self._backoff_service = backoff_service

    def assess(
        self, task_id: str, schedule_id: str = None, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleHealthResult:
        """Read-only health verdict for every one of task_id's own
        schedules, or exactly one when schedule_id is given.

        Raises:
            InvalidAgentTaskRecoveryScheduleHealthError: If task_id/
                schedule_id is not a non-empty string, now is given and
                is not a datetime, or schedule_id is given and names no
                recorded schedule for task_id
        """
        self._require_text(task_id, "task_id")
        now = self._resolve_now(now)

        all_schedules = self._scheduling_service.list(task_id)
        duplicate_ids = self._detect_duplicate_active_schedules(all_schedules)

        if schedule_id is not None:
            self._require_text(schedule_id, "schedule_id")
            schedule = next((s for s in all_schedules if s.schedule_id == schedule_id), None)
            if schedule is None:
                raise InvalidAgentTaskRecoveryScheduleHealthError(
                    f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
                )
            targets = [schedule]
        else:
            targets = all_schedules

        issues = []
        for schedule in targets:
            issues.extend(self._assess_schedule(task_id, schedule, now, duplicate_ids))

        status = _overall({issue.severity for issue in issues})
        return AgentTaskRecoveryScheduleHealthResult(
            task_id=task_id, schedule_id=schedule_id, status=status, issues=tuple(issues), assessed_at=now
        )

    def summary(self, task_id: str, now: Optional[datetime] = None) -> AgentTaskRecoveryScheduleHealthSummary:
        """Task-wide health rollup -- exactly assess(task_id) (every
        schedule), plus schedule/issue counts.

        Raises:
            InvalidAgentTaskRecoveryScheduleHealthError: If task_id is
                not a non-empty string, or now is given and is not a
                datetime
        """
        self._require_text(task_id, "task_id")
        now = self._resolve_now(now)

        result = self.assess(task_id, now=now)
        schedule_count = len(self._scheduling_service.list(task_id))
        return AgentTaskRecoveryScheduleHealthSummary(
            task_id=task_id, status=result.status, schedule_count=schedule_count,
            issue_count=len(result.issues), issues=result.issues, assessed_at=now,
        )

    def _assess_schedule(self, task_id: str, schedule, now: datetime, duplicate_ids: set) -> list:
        if schedule.status == CANCELLED:
            return []

        schedule_id = schedule.schedule_id
        issues = []

        if schedule.status == INVALIDATED:
            issues.append(
                self._issue(
                    "invalidated", DEGRADED, schedule_id,
                    "schedule's authorization/preflight is no longer valid", ("effective_status=invalidated",),
                )
            )

        if schedule_id in duplicate_ids:
            issues.append(
                self._issue(
                    "duplicate_active_schedule", DEGRADED, schedule_id,
                    "a duplicate active schedule exists for this preflight_id",
                    (f"preflight_id={schedule.preflight_id}",),
                )
            )

        if self._expiration_service is not None:
            expiration = self._expiration_service.check(task_id, schedule_id, now=now)
            if expiration.state == EXPIRED:
                issues.append(
                    self._issue("expired", DEGRADED, schedule_id, expiration.reason, (f"deadline={expiration.deadline}",))
                )

        plan = self._recovery_service.plan_recovery(task_id, schedule_id, now=now)
        if plan.action in (REDISPATCH, COMPLETE_HANDOFF):
            issues.append(
                self._issue("orphaned_dispatch", DEGRADED, schedule_id, plan.reason, (f"recovery_action={plan.action}",))
            )
        elif plan.action == RECOVERY_BLOCKED:
            issues.append(self._issue("inconsistent_schedule_state", HEALTH_BLOCKED, schedule_id, plan.reason, ()))

        if self._capacity_service is not None:
            capacity = self._capacity_service.check(task_id, schedule_id)
            if capacity.blocking_reasons:
                issues.append(
                    self._issue(
                        "capacity_blocked", DEGRADED, schedule_id,
                        "; ".join(capacity.blocking_reasons), tuple(capacity.blocking_reasons),
                    )
                )

        if self._backoff_service is not None:
            backoff = self._backoff_service.calculate(task_id, schedule_id, now=now)
            if backoff.dead_letter_required:
                issues.append(
                    self._issue(
                        "retry_exhausted", HEALTH_BLOCKED, schedule_id,
                        "recovery retry attempts are exhausted per existing retry policy",
                        (f"remaining_attempts={backoff.remaining_attempts}",),
                    )
                )
            elif backoff.attempt and backoff.attempt > 1:
                issues.append(
                    self._issue(
                        "repeated_backoff", DEGRADED, schedule_id,
                        f"schedule has required {backoff.attempt - 1} prior retry attempt(s)",
                        (f"attempt={backoff.attempt}",),
                    )
                )

        return issues

    @staticmethod
    def _detect_duplicate_active_schedules(schedules: list) -> set:
        seen_preflight_ids: set = set()
        duplicates: set = set()
        for schedule in schedules:
            if schedule.status == CANCELLED:
                continue
            if schedule.preflight_id in seen_preflight_ids:
                duplicates.add(schedule.schedule_id)
            else:
                seen_preflight_ids.add(schedule.preflight_id)
        return duplicates

    @staticmethod
    def _issue(code, severity, schedule_id, reason, evidence) -> AgentTaskRecoveryScheduleHealthIssue:
        return AgentTaskRecoveryScheduleHealthIssue(
            code=code, severity=severity, schedule_id=schedule_id, reason=reason, evidence=tuple(evidence)
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleHealthError(f"{field_name} is required and must be a non-empty string")

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleHealthError("now must be a datetime when given")
        return now
