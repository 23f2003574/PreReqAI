from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .dispatch import (
    AgentTaskRecoveryScheduleDispatch,
    InvalidAgentTaskRecoveryScheduleDispatchError,
    LLMAgentTaskRecoveryPreflightScheduleDispatchService,
)
from .expiration import EXPIRED, LLMAgentTaskRecoveryPreflightScheduleExpirationService
from .models import CANCELLED, INVALIDATED, SCHEDULED
from .reconciliation import LLMAgentTaskRecoveryPreflightScheduleReconciliationService
from .service import LLMAgentTaskRecoveryPreflightSchedulingService
from .validation import LLMAgentTaskRecoveryPreflightScheduleValidationService

REDISPATCH = "redispatch"
COMPLETE_HANDOFF = "complete_handoff"
NO_ACTION_REQUIRED = "none"
BLOCKED = "blocked"
RECOVERY_ACTIONS = frozenset({REDISPATCH, COMPLETE_HANDOFF, NO_ACTION_REQUIRED, BLOCKED})


class InvalidAgentTaskRecoveryScheduleRecoveryError(ValueError):
    """Raised when plan_recovery()/recover() is given invalid arguments,
    names a schedule that does not exist for task_id, or recover() is
    asked to act on a schedule whose state cannot be safely reconstructed
    (Rule: "Fail closed when the state cannot be safely reconstructed")."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleRecoveryPlan:
    """plan_recovery()'s read-only, explainable verdict -- re-derived
    fresh on every call, never persisted. `recoverable` is exactly
    `action in (REDISPATCH, COMPLETE_HANDOFF)`."""

    task_id: str
    schedule_id: str
    recoverable: bool
    action: str
    reason: str
    planned_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleRecoveryResult:
    """recover()'s complete report of one recovery attempt. `dispatch` is
    the resulting or already-existing Commit #3 dispatch record, or None
    if the schedule was never dispatched at all (a pure no-op)."""

    task_id: str
    schedule_id: str
    action_taken: str
    repaired: bool
    dispatch: Optional[AgentTaskRecoveryScheduleDispatch]
    reason: str
    recovered_at: datetime


class LLMAgentTaskRecoveryPreflightScheduleRecoveryService:
    """Repairs interrupted/orphaned SCHEDULING state -- never a second
    recovery mechanism (Rule: "Do not invent a second recovery
    mechanism"): the ONLY mutations anywhere in this class are Commit
    #4's own already-idempotent `reconcile()` and Commit #3's own
    already-idempotent `dispatch()`, plus (for a dispatch record whose
    own queue handoff never completed) a direct call to the SAME
    duck-typed `queue_service.enqueue()` collaborator Commit #3 itself
    accepts -- reused here directly rather than through Commit #3, since
    Commit #3's own `dispatch()` is idempotent by (task_id, schedule_id)
    and would simply return the existing, still-incomplete record
    unchanged rather than retry the handoff.

    `queue_service.enqueue()` is itself already idempotent (a second call
    for an already-queued task_id returns its existing entry, never a
    duplicate) -- Rule 4 ("Recovery must be idempotent: never create
    duplicate dispatches") therefore holds for BOTH branches without this
    class tracking anything of its own: REDISPATCH only ever runs when no
    dispatch record exists yet, and COMPLETE_HANDOFF's own enqueue() call
    is safe to repeat as many times as plan_recovery() keeps reporting it
    (Rule 4).

    Reconciles first (Rule 1: "Reconcile current state before recovery"):
    recover() always runs Commit #4's own `reconcile()` for this exact
    schedule_id before planning anything, so a schedule that has actually
    gone invalid/duplicate/superseded since it was last read is cancelled
    (and therefore reads as NO_ACTION_REQUIRED, never recoverable) before
    a stale plan could act on it. plan_recovery() itself never reconciles
    (Rule: "plan_recovery() must be read-only") -- it only reads Commit
    #1's own effective status, Commit #8's own expiration check() (when
    wired), and Commit #2's own validate(), none of which write anything.

    Never recovers a cancelled/superseded (Commit #1's own effective
    CANCELLED), revoked/invalidated (Commit #1's own effective
    INVALIDATED), or expired (Commit #8's own check(), when wired)
    schedule (Rule 2) -- each reads as NO_ACTION_REQUIRED, not
    recoverable, and recover() is a pure no-op for it: nothing is
    dispatched, nothing raises.

    Fails closed (Rule 8) rather than guessing in two distinct ways: a
    schedule whose own dispatch history is ambiguous (more than one
    dispatch record was ever recorded for it -- should never happen
    through Commit #3's own idempotent `dispatch()`, but this class
    refuses to pick one if it ever does) is BLOCKED; a due schedule whose
    own Commit #2 validation fails for a reason not already covered above
    (an authorization state this class does not itself understand) is
    also BLOCKED rather than silently redispatched.

    Preserves the original schedule (Rule: "Preserve the original
    schedule and record what was repaired"): no operation here ever
    mutates Commit #1's own stored schedule record -- what was repaired
    is reported entirely through this call's own
    AgentTaskRecoveryScheduleRecoveryResult, exactly the same "describe
    the repair as data, don't rewrite history" discipline Commit #8's own
    expiration (cancellation reason) and Commit #4's own reconciliation
    entries already establish.

    Never executes recovery (Rule: "must not execute the underlying
    recovery task"): nothing here calls anything from
    agent_task_event_analytics' own execution service or Commit #11-of-
    agent_task_recovery_guardrails' own consumption service -- REDISPATCH
    and COMPLETE_HANDOFF only ever move scheduling/dispatch state.
    """

    def __init__(
        self,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        dispatch_service: LLMAgentTaskRecoveryPreflightScheduleDispatchService = None,
        validation_service: LLMAgentTaskRecoveryPreflightScheduleValidationService = None,
        reconciliation_service: LLMAgentTaskRecoveryPreflightScheduleReconciliationService = None,
        expiration_service: LLMAgentTaskRecoveryPreflightScheduleExpirationService = None,
        queue_service=None,
    ):
        """
        Args:
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService.
            dispatch_service: Defaults to a fresh Commit #3 service built
                over scheduling_service.
            validation_service: Defaults to a fresh Commit #2 service
                built over scheduling_service.
            reconciliation_service: Defaults to a fresh Commit #4 service
                built over scheduling_service/dispatch_service.
            expiration_service: Optional Commit #8
                LLMAgentTaskRecoveryPreflightScheduleExpirationService --
                when given, an expired schedule is never recovered.
            queue_service: Optional duck-typed collaborator with
                `enqueue(task_id)`, used only to complete an already-
                dispatched schedule's missing queue handoff -- when
                omitted, that case is reported BLOCKED rather than
                silently skipped, since the handoff genuinely cannot be
                completed.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._dispatch_service = (
            dispatch_service
            if dispatch_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDispatchService(scheduling_service=self._scheduling_service)
        )
        self._validation_service = (
            validation_service
            if validation_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleValidationService(scheduling_service=self._scheduling_service)
        )
        self._reconciliation_service = (
            reconciliation_service
            if reconciliation_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleReconciliationService(
                scheduling_service=self._scheduling_service, dispatch_service=self._dispatch_service
            )
        )
        self._expiration_service = expiration_service
        self._queue_service = queue_service

    def find_recoverable(self, task_id: str, now: Optional[datetime] = None) -> tuple:
        """Every one of task_id's own SCHEDULED schedules currently
        recoverable (REDISPATCH or COMPLETE_HANDOFF) -- a pure, read-only
        query.

        Raises:
            InvalidAgentTaskRecoveryScheduleRecoveryError: If task_id is
                not a non-empty string, or now is given and is not a
                datetime
        """
        self._require_text(task_id, "task_id")
        now = self._resolve_now(now)

        recoverable = []
        for schedule in self._scheduling_service.list(task_id):
            if schedule.status != SCHEDULED:
                continue
            plan = self.plan_recovery(task_id, schedule.schedule_id, now=now)
            if plan.recoverable:
                recoverable.append(schedule)
        return tuple(recoverable)

    def plan_recovery(
        self, task_id: str, schedule_id: str, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleRecoveryPlan:
        """Read-only recovery plan for task_id's exact schedule_id,
        re-derived fresh every call. Never reconciles or mutates
        anything.

        Raises:
            InvalidAgentTaskRecoveryScheduleRecoveryError: If task_id/
                schedule_id is not a non-empty string, now is given and
                is not a datetime, or schedule_id names no recorded
                schedule for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        now = self._resolve_now(now)

        schedule = self._scheduling_service.get(task_id, schedule_id)
        if schedule is None:
            raise InvalidAgentTaskRecoveryScheduleRecoveryError(
                f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
            )

        if schedule.status == CANCELLED:
            return self._plan(task_id, schedule_id, NO_ACTION_REQUIRED, "schedule has been cancelled or superseded", now)
        if schedule.status == INVALIDATED:
            return self._plan(
                task_id, schedule_id, NO_ACTION_REQUIRED, "schedule is no longer authorized (revoked/invalidated)", now
            )

        if self._expiration_service is not None:
            expiration = self._expiration_service.check(task_id, schedule_id, now=now)
            if expiration.state == EXPIRED:
                return self._plan(task_id, schedule_id, NO_ACTION_REQUIRED, "schedule has expired", now)

        dispatches = [d for d in self._dispatch_service.list(task_id) if d.schedule_id == schedule_id]
        if len(dispatches) > 1:
            return self._plan(
                task_id, schedule_id, BLOCKED,
                "ambiguous dispatch state: more than one dispatch record exists for this schedule", now,
            )

        if dispatches:
            dispatch = dispatches[0]
            if dispatch.queue_reference is not None:
                return self._plan(
                    task_id, schedule_id, NO_ACTION_REQUIRED, "schedule has already been fully dispatched", now
                )
            if self._queue_service is None:
                return self._plan(
                    task_id, schedule_id, BLOCKED,
                    "dispatch was recorded but the queue handoff never completed, and no queue_service is "
                    "configured to complete it",
                    now,
                )
            return self._plan(
                task_id, schedule_id, COMPLETE_HANDOFF,
                "dispatch was recorded but the queue handoff never completed", now,
            )

        if schedule.execute_at is not None and now < schedule.execute_at:
            return self._plan(task_id, schedule_id, NO_ACTION_REQUIRED, "execution window has not been reached yet", now)

        # Commit #2's own validate() re-derives its window check against
        # real wall-clock time (it takes no injectable `now`), which this
        # class's own deterministic due-check above already renders moot
        # -- so that one specific reason is never treated as a fresh
        # blocker here, only genuinely unexpected ones (Rule: "Fail
        # closed" for anything this class does not itself understand).
        validation = self._validation_service.validate(task_id, schedule_id)
        remaining_reasons = [r for r in validation.blocking_reasons if "execution window" not in r]
        if not remaining_reasons:
            return self._plan(task_id, schedule_id, REDISPATCH, "schedule was never dispatched", now)

        return self._plan(
            task_id, schedule_id, BLOCKED, "cannot safely determine recovery: " + "; ".join(remaining_reasons), now,
        )

    def recover(self, task_id: str, schedule_id: str, now: Optional[datetime] = None) -> AgentTaskRecoveryScheduleRecoveryResult:
        """Repair task_id's exact schedule_id's scheduling state, if
        currently recoverable. Idempotent: never creates a duplicate
        dispatch, and a repeat call once nothing is left to repair is a
        pure no-op.

        Raises:
            InvalidAgentTaskRecoveryScheduleRecoveryError: If task_id/
                schedule_id is not a non-empty string, now is given and
                is not a datetime, schedule_id names no recorded schedule
                for task_id, or the schedule's state cannot be safely
                reconstructed (ambiguous dispatch history, or an
                unrecognized validation failure)
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        now = self._resolve_now(now)

        self._reconciliation_service.reconcile(task_id, schedule_id)
        plan = self.plan_recovery(task_id, schedule_id, now=now)

        if not plan.recoverable:
            if plan.action == BLOCKED:
                raise InvalidAgentTaskRecoveryScheduleRecoveryError(
                    f"schedule {schedule_id!r} cannot be safely recovered: {plan.reason}"
                )
            return AgentTaskRecoveryScheduleRecoveryResult(
                task_id=task_id, schedule_id=schedule_id, action_taken=NO_ACTION_REQUIRED, repaired=False,
                dispatch=self._existing_dispatch(task_id, schedule_id), reason=plan.reason, recovered_at=now,
            )

        if plan.action == REDISPATCH:
            try:
                dispatch = self._dispatch_service.dispatch(task_id, schedule_id)
            except InvalidAgentTaskRecoveryScheduleDispatchError as error:
                raise InvalidAgentTaskRecoveryScheduleRecoveryError(
                    f"schedule {schedule_id!r} could not be recovered: {error}"
                ) from error
            return AgentTaskRecoveryScheduleRecoveryResult(
                task_id=task_id, schedule_id=schedule_id, action_taken=REDISPATCH, repaired=True,
                dispatch=dispatch, reason=plan.reason, recovered_at=now,
            )

        if self._queue_service is None:
            raise InvalidAgentTaskRecoveryScheduleRecoveryError(
                f"schedule {schedule_id!r} needs its queue handoff completed, but no queue_service is configured"
            )
        try:
            self._queue_service.enqueue(task_id)
        except Exception as error:
            raise InvalidAgentTaskRecoveryScheduleRecoveryError(
                f"schedule {schedule_id!r} could not complete its queue handoff: {error}"
            ) from error
        return AgentTaskRecoveryScheduleRecoveryResult(
            task_id=task_id, schedule_id=schedule_id, action_taken=COMPLETE_HANDOFF, repaired=True,
            dispatch=self._existing_dispatch(task_id, schedule_id), reason=plan.reason, recovered_at=now,
        )

    def _existing_dispatch(self, task_id: str, schedule_id: str):
        matches = [d for d in self._dispatch_service.list(task_id) if d.schedule_id == schedule_id]
        return matches[0] if matches else None

    @staticmethod
    def _plan(task_id, schedule_id, action, reason, now) -> AgentTaskRecoveryScheduleRecoveryPlan:
        return AgentTaskRecoveryScheduleRecoveryPlan(
            task_id=task_id, schedule_id=schedule_id, recoverable=action in (REDISPATCH, COMPLETE_HANDOFF),
            action=action, reason=reason, planned_at=now,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleRecoveryError(
                f"{field_name} is required and must be a non-empty string"
            )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleRecoveryError("now must be a datetime when given")
        return now
