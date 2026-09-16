from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.agent_task_recovery_scheduling import (
    CANCELLED,
    INVALIDATED,
    LLMAgentTaskRecoveryPreflightSchedulingService,
)

from .blocking import BLOCK_STATUS_BLOCKED
from .service import LLMAgentTaskRecoveryPreflightScheduleDependencyService

# How long a schedule may remain dependency-blocked before its own wait
# is considered timed out -- a plain TTL past whenever it most recently
# started waiting (see _wait_started_at()'s own docstring), the same
# "reference timestamp + max age <= now" shape backend.
# agent_task_recovery_scheduling.expiration.DEFAULT_SCHEDULE_EXPIRATION_TTL
# already establishes for general schedule staleness (24h) -- shorter
# here, since a dependency that has not resolved in hours is a much
# stronger signal something is genuinely stuck than a schedule merely
# sitting DUE, and longer than this package's own Commit #4
# DEFAULT_DEPENDENCY_WAIT_INTERVAL (15min) recheck cadence, which this
# is not a replacement for.
DEFAULT_DEPENDENCY_WAIT_TIMEOUT = timedelta(hours=6)

_WAIT_TIMEOUT_REASON_PREFIX = "dependency wait timed out: "

ACTIVE = "active"
TIMED_OUT = "timed_out"
NOT_WAITING = "not_waiting"
NOT_APPLICABLE = "not_applicable"
TIMEOUT_STATES = frozenset({ACTIVE, TIMED_OUT, NOT_WAITING, NOT_APPLICABLE})


class InvalidAgentTaskRecoveryScheduleDependencyTimeoutError(ValueError):
    """Raised when check()/expire_wait() is given invalid arguments,
    names a schedule that does not exist for task_id, or expire_wait()
    is asked to expire a wait that is not currently timed out."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleDependencyTimeoutResult:
    """check()'s read-only, explainable verdict -- re-derived fresh on
    every call, never cached (Rule: "Distinguish an active wait from a
    genuinely timed-out wait").

    ready/blockers are the shape backend.agent_task_recovery_scheduling.
    LLMAgentTaskRecoveryPreflightScheduleValidationService's own
    optional, duck-typed dependency_service hook already expects (Rule:
    "Integrate with existing schedule validation so timed-out waits
    cannot later dispatch accidentally") -- ready is exactly
    `state in (NOT_WAITING, NOT_APPLICABLE)`; for ACTIVE/TIMED_OUT,
    blockers carries this package's own Commit #1/#2 dependency
    evidence (Rule: "Preserve dependency evidence"), with one extra
    entry naming the timeout itself once TIMED_OUT.

    state is exactly one of TIMEOUT_STATES:
        active: currently dependency-blocked, still within its own wait
            deadline.
        timed_out: currently dependency-blocked, and has been since
            before deadline -- Rule: "A timed-out wait must become
            non-dispatchable" (ready is False here specifically because
            of the timeout, not only the underlying dependency).
        not_waiting: dependencies are currently ready -- nothing to
            time out (Rule: "Respect ... completed ... schedules").
        not_applicable: the schedule itself is cancelled, unauthorized,
            already dispatched, or already expired via Commit #9-of-
            agent_task_recovery_scheduling -- none of those are this
            service's own concern to re-diagnose (Rule: "Respect
            already-cancelled, completed, expired, or dispatched
            schedules" / "Reuse existing schedule expiration ...
            conventions").

    wait_started_at/deadline are None for not_waiting/not_applicable
    (there is no wait to measure).
    """

    task_id: str
    schedule_id: str
    preflight_id: Optional[str]
    ready: bool
    state: str
    blockers: tuple
    dependency_evidence: tuple
    wait_started_at: Optional[datetime]
    deadline: Optional[datetime]
    reason: str
    checked_at: datetime

    @property
    def timed_out(self) -> bool:
        return self.state == TIMED_OUT


class LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService:
    """Detects a schedule whose dependency wait has gone on too long,
    and -- only when asked to -- ends it the exact same way backend.
    agent_task_recovery_scheduling's own Commit #9 expiration service
    ends an overdue schedule: cancel() with a reason, never a second
    timeout/state-transition framework (Rule: "Do not invent another
    timeout framework" / "Reuse existing schedule expiration/state-
    transition conventions"). No new store exists anywhere in this
    module: dependency evidence comes from this package's own Commit
    #1/#2 dependency_service.check(), wait history from Commit #3's own
    already-persisted block records (read-only), and the timeout reason
    itself is preserved for free as Commit #1-of-agent_task_recovery_
    scheduling's own already-durable cancellation_reason on the
    cancelled record cancel() produces (Rule: "Preserve dependency
    evidence, wait history, and timeout reason").

    check() never mutates anything (Rule): every collaborator it calls
    is itself read-only. It measures a wait's own age from
    _wait_started_at() -- Commit #3's own block record for this exact
    schedule_id when one currently, contiguously stands (the
    unambiguous "since when has THIS schedule_id been durably blocked"
    signal that record already establishes), falling back to the
    schedule's own created_at when no blocking_service is configured or
    this schedule_id was never explicitly blocked through it.

    expire_wait() only ever succeeds when check() itself currently
    reports TIMED_OUT (Rule: "A timed-out wait must become non-
    dispatchable") -- exactly Commit #9's own expire()/check() shape,
    reused verbatim: NOT_APPLICABLE is an idempotent no-op returning the
    schedule unchanged (Rule: "Respect already-cancelled/completed/
    expired/dispatched schedules... Make timeout handling idempotent"),
    any other non-timed-out state raises, and the ONE write anywhere in
    this class is Commit #1's own already-idempotent cancel() -- never
    schedule() again (Rule: "Never ... silently reschedule it"), never
    anything from backend.agent_task_queue_retry_scheduler's own write
    path (Rule: "Do not consume a recovery retry solely because the
    dependency wait timed out"), and never anything from Commit #11-of-
    agent_task_recovery_guardrails' own consumption service or
    agent_task_event_analytics' own execution service (Rule: "Never
    execute recovery").

    Idempotent by construction (Rule): calling expire_wait() again on a
    schedule this class (or anything else) already cancelled is a pure
    no-op -- check() reports NOT_APPLICABLE for an already-CANCELLED
    schedule, exactly Commit #9's own convention.

    check()'s own ready/blockers already integrate with dispatch
    eligibility the moment a caller wires this service (in place of, or
    chained after, this package's own Commit #1/#2/#3/#5) into Commit
    #2-of-agent_task_recovery_scheduling's own validation_service's
    optional dependency_service hook (Rule: "Integrate with existing
    schedule validation so timed-out waits cannot later dispatch
    accidentally") -- a genuinely timed-out wait blocks dispatch on its
    own, even before expire_wait() is ever explicitly called.
    """

    def __init__(
        self,
        dependency_service: LLMAgentTaskRecoveryPreflightScheduleDependencyService = None,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        blocking_service=None,
        expiration_service=None,
        dispatch_service=None,
        max_wait_duration: timedelta = None,
    ):
        """
        Args:
            dependency_service: This package's own Commit #1 gate,
                Commit #2 reconciliation service, Commit #3 blocking
                service, or Commit #5 wake service -- any already
                expose the identical check(task_id, schedule_id) ->
                .ready/.blockers shape. Defaults to a fresh Commit #1
                LLMAgentTaskRecoveryPreflightScheduleDependencyService
                (no dependency_resolver of its own -- always reports
                ready, so check() would then always report not_waiting;
                pass the real, wired instance for this service to ever
                find a genuine wait at all).
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService; used to
                build defaults and for every schedule read/write.
            blocking_service: No default. When given, its own durable
                block history (for this exact schedule_id) is used to
                measure when the current wait actually began; without
                one, every wait is measured from the schedule's own
                created_at instead.
            expiration_service: No default (mirrors this package's own
                Commit #3/#4/#5). When given, an already-Commit-#9-
                expired schedule reports not_applicable here (that
                series' own mechanism already owns it); when omitted,
                that check is simply skipped.
            dispatch_service: No default. When given, an already-
                dispatched schedule reports not_applicable here; when
                omitted, that check is simply skipped.
            max_wait_duration: Defaults to
                DEFAULT_DEPENDENCY_WAIT_TIMEOUT.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._dependency_service = (
            dependency_service
            if dependency_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDependencyService(scheduling_service=self._scheduling_service)
        )
        self._blocking_service = blocking_service
        self._expiration_service = expiration_service
        self._dispatch_service = dispatch_service
        self._max_wait_duration = max_wait_duration if max_wait_duration is not None else DEFAULT_DEPENDENCY_WAIT_TIMEOUT

    def check(
        self, task_id: str, schedule_id: str, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleDependencyTimeoutResult:
        """Read-only timeout verdict for task_id's exact schedule_id,
        re-evaluated fresh every call.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyTimeoutError: If
                task_id/schedule_id is not a non-empty string, now is
                given and is not a datetime, or schedule_id names no
                recorded schedule for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        now = self._resolve_now(now)

        schedule = self._scheduling_service.get(task_id, schedule_id)
        if schedule is None:
            raise InvalidAgentTaskRecoveryScheduleDependencyTimeoutError(
                f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
            )

        not_applicable = self._not_applicable_reason(task_id, schedule, now)
        if not_applicable is not None:
            return self._result(task_id, schedule, NOT_APPLICABLE, True, (), (), None, None, not_applicable, now)

        dependency_result = self._dependency_service.check(task_id, schedule_id)
        if dependency_result.ready:
            return self._result(
                task_id, schedule, NOT_WAITING, True, (), (), None, None, "dependencies are currently ready", now
            )

        wait_started_at = self._wait_started_at(task_id, schedule)
        deadline = wait_started_at + self._max_wait_duration
        evidence = tuple(dependency_result.blockers)

        if now < deadline:
            reason = f"waiting since {wait_started_at.isoformat()}, deadline {deadline.isoformat()}"
            return self._result(task_id, schedule, ACTIVE, False, evidence, evidence, wait_started_at, deadline, reason, now)

        reason = (
            f"dependency wait exceeded {self._max_wait_duration} "
            f"(started {wait_started_at.isoformat()}, deadline {deadline.isoformat()})"
        )
        blockers = (reason,) + evidence
        return self._result(
            task_id, schedule, TIMED_OUT, False, blockers, evidence, wait_started_at, deadline, reason, now
        )

    def expire_wait(
        self, task_id: str, schedule_id: str, reason: Optional[str] = None, now: Optional[datetime] = None
    ):
        """End task_id's exact schedule_id's dependency wait, if it is
        currently timed out. Idempotent: a schedule already cancelled,
        unauthorized, already dispatched, or already Commit #9-expired
        is returned unchanged, no-op.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyTimeoutError: If
                task_id/schedule_id is not a non-empty string, now is
                given and is not a datetime, schedule_id names no
                recorded schedule for task_id, or the dependency wait is
                not currently timed out (still active, not waiting at
                all, or not_applicable for a reason other than the ones
                this method already treats as an idempotent no-op)
        """
        now = self._resolve_now(now)
        result = self.check(task_id, schedule_id, now=now)

        if result.state == NOT_APPLICABLE:
            return self._scheduling_service.get(task_id, schedule_id)

        if result.state != TIMED_OUT:
            raise InvalidAgentTaskRecoveryScheduleDependencyTimeoutError(
                f"schedule {schedule_id!r}'s dependency wait is not currently timed out: {result.reason}"
            )

        expire_reason = _WAIT_TIMEOUT_REASON_PREFIX + (reason if reason is not None else result.reason)
        return self._scheduling_service.cancel(task_id, schedule_id, reason=expire_reason)

    def _not_applicable_reason(self, task_id, schedule, now) -> Optional[str]:
        if schedule.status == CANCELLED:
            return "schedule has already been cancelled"
        if schedule.status == INVALIDATED:
            return "schedule is not currently authorized"

        if self._dispatch_service is not None:
            dispatched = any(d.schedule_id == schedule.schedule_id for d in self._dispatch_service.list(task_id))
            if dispatched:
                return "schedule has already been dispatched"

        if self._expiration_service is not None:
            expiration = self._expiration_service.check(task_id, schedule.schedule_id, now=now)
            if expiration.expired:
                return f"schedule already expired: {expiration.reason}"

        return None

    def _wait_started_at(self, task_id: str, schedule) -> datetime:
        if self._blocking_service is not None:
            history = self._blocking_service.get_history(task_id, schedule.schedule_id)
            if history and history[-1].status == BLOCK_STATUS_BLOCKED:
                return history[-1].occurred_at
        return schedule.created_at

    @staticmethod
    def _result(task_id, schedule, state, ready, blockers, evidence, wait_started_at, deadline, reason, now):
        return AgentTaskRecoveryScheduleDependencyTimeoutResult(
            task_id=task_id, schedule_id=schedule.schedule_id, preflight_id=schedule.preflight_id,
            ready=ready, state=state, blockers=tuple(blockers), dependency_evidence=tuple(evidence),
            wait_started_at=wait_started_at, deadline=deadline, reason=reason, checked_at=now,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleDependencyTimeoutError(
                f"{field_name} is required and must be a non-empty string"
            )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleDependencyTimeoutError("now must be a datetime when given")
        return now
