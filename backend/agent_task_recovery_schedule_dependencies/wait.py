from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from backend.agent_task_recovery_scheduling import (
    SCHEDULED,
    AgentTaskRecoveryPreflightSchedule,
    LLMAgentTaskRecoveryPreflightSchedulingService,
    LLMAgentTaskRecoveryPreflightScheduleValidationService,
)

from .service import LLMAgentTaskRecoveryPreflightScheduleDependencyService

# How long to wait before rechecking dependencies when no
# backoff_service is supplied (or it reports no usable execute_at of
# its own) -- a plain, fixed poll interval, never a second backoff
# formula (Rule: "Do not invent a new ... retry system"). Deliberately
# shorter than backend.agent_task_recovery_scheduling.expiration's own
# DEFAULT_SCHEDULE_EXPIRATION_TTL (24h): a dependency recheck is meant
# to be cheap and frequent relative to the much coarser overall
# schedule expiration window.
DEFAULT_DEPENDENCY_WAIT_INTERVAL = timedelta(minutes=15)


class InvalidAgentTaskRecoveryScheduleDependencyWaitError(ValueError):
    """Raised when plan_wait()/apply_wait() is given invalid arguments,
    or asked to plan/apply a wait that is not currently legal (schedule
    missing, dependencies already ready, schedule cancelled/invalidated/
    stale/expired, or retry attempts exhausted per existing backoff
    policy)."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleDependencyWaitPlan:
    """plan_wait()'s read-only, explainable recommendation for how long
    task_id's exact schedule_id should defer dispatch while its
    dependencies remain unresolved -- re-derived fresh every call, never
    cached or persisted on its own (Rule: "Preserve previous schedule/
    dependency history" is satisfied by apply_wait() reusing Commit #1-
    of-agent_task_recovery_scheduling's own schedule()/cancel(), which
    already retains every past record -- a wait plan itself needs no
    separate store).

    next_check_at is derived entirely from EXISTING scheduling/backoff/
    deadline rules (Rule: "Derive the next check time from existing
    scheduling/backoff/deadline rules"): a plain DEFAULT_DEPENDENCY_WAIT_
    INTERVAL poll, raised to match Commit #7's own backoff pacing when a
    backoff_service is supplied (never lowered below it -- rechecking
    dependencies faster than recovery itself could possibly retry is
    pointless), and capped to never exceed Commit #9's own expiration
    deadline when an expiration_service is supplied (never propose a
    recheck beyond the point the schedule would already be expired).

    dependency_evidence is this exact call's own
    dependency_service.check().blockers, preserved verbatim (the same
    "independently-fetched, never trusted from the caller" evidence
    discipline this package's own Commit #2/#3 already establish).
    """

    task_id: str
    schedule_id: str
    preflight_id: str
    next_check_at: datetime
    reason: str
    dependency_evidence: tuple
    planned_at: datetime
    plan_id: str = field(default_factory=lambda: str(uuid4()))


class LLMAgentTaskRecoveryPreflightScheduleDependencyWaitService:
    """Defers a BLOCKED schedule's own dispatch to a later recheck
    window, without ever touching recovery's own retry/attempt budget
    -- never a second scheduler or retry system (Rule: "Do not create
    another scheduler or retry system"): apply_wait() moves a schedule
    to a new execute_at using ONLY Commit #1-of-agent_task_recovery_
    scheduling's own cancel()/schedule() primitives (the exact same
    cancel-then-reschedule shape that series' own Commit #7 backoff.
    reschedule() already establishes for a comparable case) -- it never
    calls backend.agent_task_queue_retry_scheduler.LLMAgentTaskRetry
    Scheduler.schedule_retry() or anything else that could consume or
    record a retry attempt (Rule: "Never consume a recovery retry
    merely because dependencies are unresolved"). A supplied
    backoff_service is used ONLY for its own read-only calculate() --
    to borrow its existing pacing math and to detect an already-
    exhausted retry budget as a hard policy limit (Rule: "Respect ...
    policy limits") -- reschedule() itself is never called.

    plan_wait() only ever succeeds when Commit #1/#2/#3's own
    dependency_service.check() currently reports NOT ready (Rule:
    "Create a wait plan only when the dependency gate reports the
    schedule is blocked") -- a schedule whose dependencies are already
    satisfied cannot be planned a wait for at all. It also respects
    every other existing validity boundary before ever proposing a
    plan (Rule: "Respect task deadlines, schedule expiration,
    cancellation, and policy limits"):
      - cancelled/invalidated/revoked/policy-blocked: Commit #2-of-
        agent_task_recovery_scheduling's own validation_service.validate()
        (built WITHOUT its own dependency_service hook here, exactly the
        same "avoid a circular/duplicated dependency opinion" reasoning
        this package's own Commit #3 blocking service already applies);
      - stale/expired: Commit #9-of-agent_task_recovery_scheduling's own
        expiration_service.check(), when supplied;
      - retry budget exhausted: Commit #7-of-agent_task_recovery_
        scheduling's own backoff_service.calculate().dead_letter_required,
        when supplied -- waiting further on a task whose recovery
        attempts are already exhausted for unrelated reasons would
        never actually help it dispatch, so plan_wait() refuses instead
        of silently deferring forever.
    Any of these failing raises, naming the reason; none of them is
    ever bypassed or re-derived a second way.

    apply_wait(task_id, schedule_id, wait_plan) only ever changes
    SCHEDULING state (Rule: "apply_wait() changes scheduling state
    only; never executes recovery") -- it never calls anything from
    agent_task_event_analytics' own execution service or Commit #11-of-
    agent_task_recovery_guardrails' own consumption service.

    Self-correcting (Rule: "A dependency that becomes ready must allow
    the normal validation/dispatch path to proceed rather than forcing
    another wait"): apply_wait() re-checks dependency_service.check()
    live, immediately before ever deferring -- if dependencies have
    become ready since wait_plan was computed, the schedule is left
    completely untouched (still SCHEDULED at its own current execute_at)
    so Commit #2-of-agent_task_recovery_scheduling's own ordinary
    validate()/dispatch() path can proceed normally, rather than
    forcing yet another deferral.

    Idempotent (Rule: "Make repeated application idempotent"): applying
    the SAME wait_plan a second time (still naming the now-superseded
    original schedule_id, which apply_wait() itself already cancelled on
    the first call) finds the schedule it already created for the same
    preflight_id -- still SCHEDULED, at the exact execute_at the first
    call already set -- and returns it unchanged, rather than cancelling
    and recreating a duplicate (Rule: "...without ... creating duplicate
    schedules").
    """

    def __init__(
        self,
        dependency_service=None,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        validation_service: LLMAgentTaskRecoveryPreflightScheduleValidationService = None,
        expiration_service=None,
        backoff_service=None,
        default_wait_interval: timedelta = None,
    ):
        """
        Args:
            dependency_service: Commit #1's gate, Commit #2's
                reconciliation service, or Commit #3's blocking service
                -- any of them already expose the identical
                check(task_id, schedule_id) -> .ready/.blockers shape.
                Defaults to a fresh Commit #1
                LLMAgentTaskRecoveryPreflightScheduleDependencyService
                (no dependency_resolver of its own -- always reports
                ready, so plan_wait() would then always refuse; pass
                the real, wired instance for this service to ever do
                anything).
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService; used to
                build a default dependency_service/validation_service
                when neither is given, and for every schedule read/
                write apply_wait() performs.
            validation_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightScheduleValidationService
                built over scheduling_service, WITHOUT its own
                dependency_service wired -- this class's own
                dependency_service already owns that opinion.
            expiration_service: No default (mirrors this package's own
                Commit #3 blocking service -- a fresh instance could
                never see real schedules). When given, plan_wait() also
                refuses a stale/expired schedule and caps next_check_at
                at its own deadline; when omitted, both are skipped.
            backoff_service: No default. When given, plan_wait() reads
                its own calculate() (read-only; reschedule() is never
                called) to pace next_check_at and to detect an
                exhausted retry budget as a hard refusal; when omitted,
                both are skipped and default_wait_interval alone paces
                every plan.
            default_wait_interval: Defaults to
                DEFAULT_DEPENDENCY_WAIT_INTERVAL.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._dependency_service = (
            dependency_service
            if dependency_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDependencyService(scheduling_service=self._scheduling_service)
        )
        self._validation_service = (
            validation_service
            if validation_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleValidationService(scheduling_service=self._scheduling_service)
        )
        self._expiration_service = expiration_service
        self._backoff_service = backoff_service
        self._default_wait_interval = (
            default_wait_interval if default_wait_interval is not None else DEFAULT_DEPENDENCY_WAIT_INTERVAL
        )

    def plan_wait(
        self, task_id: str, schedule_id: str, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleDependencyWaitPlan:
        """Compute (never apply) a wait plan for task_id's exact
        schedule_id.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyWaitError: If
                task_id/schedule_id is not a non-empty string, now is
                given and is not a datetime, schedule_id names no
                recorded schedule for task_id, dependencies are
                currently ready, the schedule is cancelled/invalidated/
                unauthorized/outside its own execution window, the
                schedule is stale/expired (when expiration_service is
                given), or recovery retry attempts are exhausted per
                existing backoff policy (when backoff_service is given)
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        now = self._resolve_now(now)

        schedule = self._scheduling_service.get(task_id, schedule_id)
        if schedule is None:
            raise InvalidAgentTaskRecoveryScheduleDependencyWaitError(
                f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
            )

        dependency_result = self._dependency_service.check(task_id, schedule_id)
        if dependency_result.ready:
            raise InvalidAgentTaskRecoveryScheduleDependencyWaitError(
                f"schedule {schedule_id!r} cannot be waited on: dependencies are currently ready"
            )

        validation = self._validation_service.validate(task_id, schedule_id)
        if not validation.valid:
            raise InvalidAgentTaskRecoveryScheduleDependencyWaitError(
                f"schedule {schedule_id!r} cannot be waited on: " + "; ".join(validation.blocking_reasons)
            )

        expiration_deadline = None
        if self._expiration_service is not None:
            expiration = self._expiration_service.check(task_id, schedule_id, now=now)
            if expiration.expired:
                raise InvalidAgentTaskRecoveryScheduleDependencyWaitError(
                    f"schedule {schedule_id!r} cannot be waited on: {expiration.reason}"
                )
            expiration_deadline = expiration.deadline

        next_check_at = now + self._default_wait_interval
        if self._backoff_service is not None:
            backoff = self._backoff_service.calculate(task_id, schedule_id, now=now)
            if backoff.dead_letter_required:
                raise InvalidAgentTaskRecoveryScheduleDependencyWaitError(
                    f"schedule {schedule_id!r} cannot be waited on: recovery retry attempts are exhausted "
                    "and this task requires dead-lettering"
                )
            if backoff.execute_at is not None:
                next_check_at = max(next_check_at, backoff.execute_at)

        if expiration_deadline is not None:
            next_check_at = min(next_check_at, expiration_deadline)
        next_check_at = max(next_check_at, now)

        return AgentTaskRecoveryScheduleDependencyWaitPlan(
            task_id=task_id, schedule_id=schedule_id, preflight_id=schedule.preflight_id,
            next_check_at=next_check_at,
            reason="dependencies are not yet ready: " + ("; ".join(dependency_result.blockers) or "blocked"),
            dependency_evidence=tuple(dependency_result.blockers), planned_at=now,
        )

    def apply_wait(
        self,
        task_id: str,
        schedule_id: str,
        wait_plan: AgentTaskRecoveryScheduleDependencyWaitPlan,
        now: Optional[datetime] = None,
    ) -> AgentTaskRecoveryPreflightSchedule:
        """Apply wait_plan (from a prior plan_wait() call) to task_id's
        exact schedule_id -- defers dispatch to wait_plan.next_check_at
        by cancelling schedule_id and creating a new schedule for the
        SAME preflight_id (Commit #1-of-agent_task_recovery_scheduling's
        own primitives), UNLESS dependencies have become ready since
        wait_plan was computed (in which case schedule_id is left
        completely untouched). Idempotent: applying the same wait_plan
        again once already applied returns the schedule it already
        created, unchanged.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyWaitError: If
                task_id/schedule_id is not a non-empty string, now is
                given and is not a datetime, wait_plan is not an
                AgentTaskRecoveryScheduleDependencyWaitPlan or does not
                name this exact task_id/schedule_id, schedule_id names
                no recorded schedule for task_id, or schedule_id is no
                longer SCHEDULED and was not superseded by a prior
                application of this exact wait_plan
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        now = self._resolve_now(now)
        if not isinstance(wait_plan, AgentTaskRecoveryScheduleDependencyWaitPlan):
            raise InvalidAgentTaskRecoveryScheduleDependencyWaitError(
                "wait_plan must be an AgentTaskRecoveryScheduleDependencyWaitPlan"
            )
        if wait_plan.task_id != task_id or wait_plan.schedule_id != schedule_id:
            raise InvalidAgentTaskRecoveryScheduleDependencyWaitError(
                "wait_plan does not name this exact task_id/schedule_id"
            )

        schedule = self._scheduling_service.get(task_id, schedule_id)
        if schedule is None:
            raise InvalidAgentTaskRecoveryScheduleDependencyWaitError(
                f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
            )

        if schedule.status != SCHEDULED:
            superseding = self._active_schedule_for_preflight(task_id, wait_plan.preflight_id)
            if superseding is not None:
                return superseding
            raise InvalidAgentTaskRecoveryScheduleDependencyWaitError(
                f"schedule {schedule_id!r} is no longer active and was not superseded by a prior wait application"
            )

        dependency_result = self._dependency_service.check(task_id, schedule_id)
        if dependency_result.ready:
            # Dependencies resolved since plan_wait() was computed --
            # never force another wait; leave the normal dispatch path
            # free to proceed.
            return schedule

        self._scheduling_service.cancel(
            task_id, schedule_id, reason=f"deferred pending dependencies: {wait_plan.reason}"
        )
        return self._scheduling_service.schedule(task_id, wait_plan.preflight_id, execute_at=wait_plan.next_check_at)

    def _active_schedule_for_preflight(self, task_id: str, preflight_id: str):
        for candidate in self._scheduling_service.list(task_id):
            if candidate.preflight_id == preflight_id and candidate.status == SCHEDULED:
                return candidate
        return None

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleDependencyWaitError(
                f"{field_name} is required and must be a non-empty string"
            )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleDependencyWaitError("now must be a datetime when given")
        return now
