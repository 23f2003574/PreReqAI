from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from .dispatch import LLMAgentTaskRecoveryPreflightScheduleDispatchService
from .health import LLMAgentTaskRecoveryPreflightScheduleHealthService
from .models import SCHEDULED
from .service import LLMAgentTaskRecoveryPreflightSchedulingService


class InvalidAgentTaskRecoveryScheduleReportingError(ValueError):
    """Raised when report()/history() is given invalid arguments, or
    schedule_id names no recorded schedule for task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleReportEntry:
    """report()'s per-schedule row -- every field is read verbatim from
    an existing durable record or an existing service's own live verdict,
    never recomputed. `issues` is exactly the subset of Commit #10's own
    health issues for this schedule_id (possibly empty)."""

    schedule_id: str
    preflight_id: str
    status: str
    created_at: datetime
    execute_at: Optional[datetime]
    age: timedelta
    dispatched: bool
    dispatch_id: Optional[str]
    queue_reference: Optional[str]
    issues: tuple


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleReport:
    """report()'s complete, read-only CURRENT-state snapshot (Rule:
    "Clearly distinguish current state from historical outcomes" -- this
    is the "current" half; history() below is the historical one).

    expired_count/capacity_blocked_count/retry_activity_count are `None`,
    never `0`, whenever this service was never wired with the
    corresponding optional collaborator (Rule: "Missing/partial history
    must be represented explicitly rather than guessed") -- `0` would
    silently claim "checked, and found none," which is not the same
    fact as "never checked at all."
    """

    task_id: str
    schedule_id: Optional[str]
    generated_at: datetime
    entries: tuple
    total_schedules: int
    status_counts: dict
    pending_count: int
    dispatched_count: int
    expired_count: Optional[int]
    capacity_blocked_count: Optional[int]
    retry_activity_count: Optional[int]
    health_status: str


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleHistoryEntry:
    """history()'s per-schedule row -- exactly what Commit #1's own
    schedule record and Commit #3's own dispatch record (if any) already
    durably hold, in the order Commit #1's own `list()` already returns
    them (oldest first) -- never re-derived or re-ordered."""

    schedule_id: str
    preflight_id: str
    status: str
    created_at: datetime
    execute_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancellation_reason: Optional[str]
    dispatched: bool
    dispatch_id: Optional[str]
    dispatched_at: Optional[datetime]
    queue_reference: Optional[str]


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleHistoryReport:
    """history()'s complete, read-only, chronological (oldest-first)
    timeline of every schedule task_id has ever had -- the HISTORICAL
    half of the current/historical split report() and history() together
    provide."""

    task_id: str
    generated_at: datetime
    entries: tuple
    total_schedules: int


class LLMAgentTaskRecoveryPreflightScheduleReportingService:
    """Read-only operational report over already-persisted scheduling
    state -- never a second reporting/analytics framework (Rule: "Do not
    create a new reporting/analytics framework"): every number and status
    in this class is read straight from Commit #1's own schedule records,
    Commit #3's own dispatch records, or Commit #10's own health
    `assess()` -- nothing here recomputes a metric an existing service
    already owns.

    In particular, expiration/capacity/backoff/recovery-orphan signals
    ("dispatch/recovery failures," "retry/backoff activity," "capacity/
    admission failures" -- Rule: "reuse existing ... expiration,
    reconciliation, health, ... recovery-history services") are reused
    ENTIRELY THROUGH Commit #10's own health `assess()` rather than
    integrated a second time directly against Commit #6/#7/#8/#9's own
    services -- assess() already combines exactly those into one
    read-only, per-schedule issue list; re-wiring each of them again
    here would itself be the "duplicated calculation" Rule 2 forbids.
    The optional `expiration_service`/`capacity_service`/`backoff_service`
    constructor args passed here exist ONLY to tell this class whether
    that category of signal was ever tracked at all (so report() can
    report `None`, not a possibly-wrong `0`, for it) -- their own
    check()/calculate() methods are never called a second time by this
    class; only Commit #10's own health_service (wired with the SAME
    instances) actually calls them.

    report() vs history() (Rule: "Clearly distinguish current state from
    historical outcomes"): report() is a present-moment snapshot --
    current effective status, current dispatch state, current health --
    optionally scoped to one schedule_id; history() is the complete,
    unscoped, chronological record of every schedule task_id has ever
    had, including cancelled/superseded ones, with no health
    re-assessment (health is a "now" concept, not a historical one).

    Never mutates, executes, or repairs anything (Rule: "No execution,
    scheduling mutation, or automatic repair") -- every method here is a
    pure read.
    """

    def __init__(
        self,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        dispatch_service: LLMAgentTaskRecoveryPreflightScheduleDispatchService = None,
        health_service: LLMAgentTaskRecoveryPreflightScheduleHealthService = None,
        expiration_service=None,
        capacity_service=None,
        backoff_service=None,
    ):
        """
        Args:
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService.
            dispatch_service: Defaults to a fresh Commit #3 service built
                over scheduling_service.
            health_service: Defaults to a fresh Commit #10 service built
                over scheduling_service/dispatch_service and the three
                optional collaborators below.
            expiration_service, capacity_service, backoff_service:
                Optional -- passed through to a default-constructed
                health_service, and their mere presence (never a second
                call to any of them) determines whether report()'s own
                expired_count/capacity_blocked_count/retry_activity_count
                are tracked (an int) or untracked (`None`). Ignored when
                an explicit health_service is supplied.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._dispatch_service = (
            dispatch_service
            if dispatch_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDispatchService(scheduling_service=self._scheduling_service)
        )
        self._health_service = (
            health_service
            if health_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleHealthService(
                scheduling_service=self._scheduling_service, dispatch_service=self._dispatch_service,
                expiration_service=expiration_service, capacity_service=capacity_service,
                backoff_service=backoff_service,
            )
        )
        self._tracks_expiration = expiration_service is not None
        self._tracks_capacity = capacity_service is not None
        self._tracks_backoff = backoff_service is not None

    def report(
        self, task_id: str, schedule_id: str = None, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleReport:
        """Current-state operational report for every one of task_id's
        own schedules, or exactly one when schedule_id is given.

        Raises:
            InvalidAgentTaskRecoveryScheduleReportingError: If task_id/
                schedule_id is not a non-empty string, now is given and
                is not a datetime, or schedule_id is given and names no
                recorded schedule for task_id
        """
        self._require_text(task_id, "task_id")
        now = self._resolve_now(now)

        all_schedules = self._scheduling_service.list(task_id)
        if schedule_id is not None:
            self._require_text(schedule_id, "schedule_id")
            schedule = next((s for s in all_schedules if s.schedule_id == schedule_id), None)
            if schedule is None:
                raise InvalidAgentTaskRecoveryScheduleReportingError(
                    f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
                )
            targets = [schedule]
        else:
            targets = all_schedules

        health = self._health_service.assess(task_id, schedule_id=schedule_id, now=now)
        issues_by_schedule: dict = {}
        for issue in health.issues:
            issues_by_schedule.setdefault(issue.schedule_id, []).append(issue)

        dispatch_by_schedule = {d.schedule_id: d for d in self._dispatch_service.list(task_id)}

        entries = []
        status_counts: dict = {}
        for schedule in targets:
            status_counts[schedule.status] = status_counts.get(schedule.status, 0) + 1
            dispatch = dispatch_by_schedule.get(schedule.schedule_id)
            entries.append(
                AgentTaskRecoveryScheduleReportEntry(
                    schedule_id=schedule.schedule_id, preflight_id=schedule.preflight_id, status=schedule.status,
                    created_at=schedule.created_at, execute_at=schedule.execute_at, age=now - schedule.created_at,
                    dispatched=dispatch is not None,
                    dispatch_id=dispatch.dispatch_id if dispatch is not None else None,
                    queue_reference=dispatch.queue_reference if dispatch is not None else None,
                    issues=tuple(issues_by_schedule.get(schedule.schedule_id, ())),
                )
            )

        pending_count = sum(1 for e in entries if e.status == SCHEDULED and not e.dispatched)
        dispatched_count = sum(1 for e in entries if e.dispatched)
        expired_count = self._count_by_issue_code(entries, {"expired"}) if self._tracks_expiration else None
        capacity_blocked_count = (
            self._count_by_issue_code(entries, {"capacity_blocked"}) if self._tracks_capacity else None
        )
        retry_activity_count = (
            self._count_by_issue_code(entries, {"repeated_backoff", "retry_exhausted"}) if self._tracks_backoff else None
        )

        return AgentTaskRecoveryScheduleReport(
            task_id=task_id, schedule_id=schedule_id, generated_at=now, entries=tuple(entries),
            total_schedules=len(targets), status_counts=status_counts, pending_count=pending_count,
            dispatched_count=dispatched_count, expired_count=expired_count,
            capacity_blocked_count=capacity_blocked_count, retry_activity_count=retry_activity_count,
            health_status=health.status,
        )

    def history(self, task_id: str, now: Optional[datetime] = None) -> AgentTaskRecoveryScheduleHistoryReport:
        """Complete, chronological (oldest-first) history of every
        schedule task_id has ever had -- current, cancelled, or
        superseded alike.

        Raises:
            InvalidAgentTaskRecoveryScheduleReportingError: If task_id is
                not a non-empty string, or now is given and is not a
                datetime
        """
        self._require_text(task_id, "task_id")
        now = self._resolve_now(now)

        schedules = self._scheduling_service.list(task_id)
        dispatch_by_schedule = {d.schedule_id: d for d in self._dispatch_service.list(task_id)}

        entries = []
        for schedule in schedules:
            dispatch = dispatch_by_schedule.get(schedule.schedule_id)
            entries.append(
                AgentTaskRecoveryScheduleHistoryEntry(
                    schedule_id=schedule.schedule_id, preflight_id=schedule.preflight_id, status=schedule.status,
                    created_at=schedule.created_at, execute_at=schedule.execute_at,
                    cancelled_at=schedule.cancelled_at, cancellation_reason=schedule.cancellation_reason,
                    dispatched=dispatch is not None,
                    dispatch_id=dispatch.dispatch_id if dispatch is not None else None,
                    dispatched_at=dispatch.dispatched_at if dispatch is not None else None,
                    queue_reference=dispatch.queue_reference if dispatch is not None else None,
                )
            )

        return AgentTaskRecoveryScheduleHistoryReport(
            task_id=task_id, generated_at=now, entries=tuple(entries), total_schedules=len(entries)
        )

    @staticmethod
    def _count_by_issue_code(entries, codes: set) -> int:
        return sum(1 for e in entries if any(issue.code in codes for issue in e.issues))

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleReportingError(
                f"{field_name} is required and must be a non-empty string"
            )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleReportingError("now must be a datetime when given")
        return now
