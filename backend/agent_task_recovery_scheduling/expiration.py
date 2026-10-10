from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from .dispatch import LLMAgentTaskRecoveryPreflightScheduleDispatchService
from .models import CANCELLED, INVALIDATED, SCHEDULED, AgentTaskRecoveryPreflightSchedule
from .reconciliation import AgentTaskRecoveryScheduleReconciliationEntry, AgentTaskRecoveryScheduleReconciliationResult
from .service import LLMAgentTaskRecoveryPreflightSchedulingService

NOT_YET_DUE = "not_yet_due"
DUE = "due"
EXPIRED = "expired"
NOT_APPLICABLE = "not_applicable"
EXPIRATION_STATES = frozenset({NOT_YET_DUE, DUE, EXPIRED, NOT_APPLICABLE})

# How long a schedule may sit DUE (its own execute_at reached, or none
# set at all) before it is considered abandoned -- the same "TTL past a
# reference timestamp" shape backend.agent_task_queue_expiration's own
# DEFAULT_QUEUE_ENTRY_TTL already establishes for QueueEntry.queued_at,
# applied here to a schedule's own execute_at (or created_at, absent an
# execute_at). Longer than that 1-hour machine-queue dwell time -- a
# recovery schedule is a coarser-grained, often human-relevant window,
# closer in spirit to backend.agent_policy_risk_approval's own 24-hour
# DEFAULT_APPROVAL_WINDOW.
DEFAULT_SCHEDULE_EXPIRATION_TTL = timedelta(hours=24)

_EXPIRATION_REASON_PREFIX = "expired: "


class InvalidAgentTaskRecoveryScheduleExpirationError(ValueError):
    """Raised when check()/expire()/expire_due() is given invalid
    arguments, names a schedule that does not exist for task_id, or
    expire() is asked to expire a schedule that is not currently
    eligible for expiration."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleExpirationResult:
    """check()'s read-only, explainable verdict -- re-derived fresh on
    every call, never cached or persisted. `state` is exactly one of
    NOT_YET_DUE, DUE, EXPIRED, or NOT_APPLICABLE (already cancelled,
    invalidated, or dispatched -- expiration is not this class's concern
    for those); `expired` is `state == EXPIRED`."""

    task_id: str
    schedule_id: str
    state: str
    expired: bool
    deadline: Optional[datetime]
    reason: str
    checked_at: datetime


class LLMAgentTaskRecoveryPreflightScheduleExpirationService:
    """Marks overdue scheduled recovery work non-actionable -- never a
    second generic expiration framework (Rule: "Do not invent a generic
    expiration framework"): the ONLY write anywhere in this class is
    Commit #1's own already-idempotent `cancel()` -- an expired schedule
    is persisted exactly the same way a manually-cancelled one is (Rule:
    "record expiration state/reason using existing history conventions"),
    which for free gets it blocked by every existing CANCELLED check
    already in this series (Commit #2's own dispatch validation, Commit
    #6's own capacity check, Commit #7's own backoff calculate()) without
    touching any of them (Rule: "Expired schedules must never dispatch").

    Deadline comes from two existing sources, never a new formula (Rule:
    "Determine expiration from existing schedule/task deadlines and
    recovery policy constraints"):
      - a TTL past the schedule's own execute_at (or created_at, absent
        one) -- the exact same "reference timestamp + max age <= now"
        shape backend.agent_task_queue_expiration's own
        LLMAgentTaskQueueExpirationService already establishes for
        QueueEntry.queued_at, applied here instead to this package's own
        Commit #1 record.
      - optionally, Commit #7's own backoff calculate()'s own
        dead_letter_required (retry attempts exhausted per the existing
        recovery/retry policy) -- when wired, this alone also expires a
        schedule regardless of how recently it became due.

    Respects already-cancelled, invalidated, or dispatched schedules
    (Rule): check() reports NOT_APPLICABLE for any of those without
    evaluating a deadline at all, and expire() is a pure idempotent no-op
    for them (never raises, never re-cancels) -- exactly the "protect a
    record that is no longer this service's business" precedent Commit
    #4's own reconciliation already establishes for dispatched schedules.
    A schedule whose execution window has not yet arrived is NOT_YET_DUE,
    never DUE or EXPIRED (Rule: "Distinguish not-yet-due, due/eligible,
    and expired states").

    expire() is idempotent (Rule): calling it again on a schedule it has
    already expired (now CANCELLED) is a no-op returning the current
    record, the same "already terminal, nothing left to do" no-op every
    other write in this series already establishes; calling it on one
    that genuinely is not yet eligible for expiration raises instead,
    since forcing that would silently discard a still-live schedule.

    expire_due() reuses Commit #4's own reconciliation result shape
    verbatim (Rule: "Reuse existing scheduling/reconciliation
    infrastructure") -- it is exactly a reconciliation pass whose only
    trigger is deadline expiry rather than authorization invalidity, and
    only ever calls expire() for a schedule check() itself already
    reports EXPIRED (Rule: "process only schedules actually eligible for
    expiration").

    Never executes recovery or reschedules (Rule): nothing here calls
    Commit #7's own reschedule(), Commit #11-of-agent_task_recovery_
    guardrails' own consumption service, or anything from
    agent_task_event_analytics' own execution service -- an expired
    schedule simply becomes CANCELLED and stays that way.
    """

    def __init__(
        self,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        dispatch_service: LLMAgentTaskRecoveryPreflightScheduleDispatchService = None,
        backoff_service=None,
        max_overdue_age: timedelta = None,
    ):
        """
        Args:
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService.
            dispatch_service: Optional Commit #3
                LLMAgentTaskRecoveryPreflightScheduleDispatchService --
                when given, an already-dispatched schedule is reported
                NOT_APPLICABLE rather than evaluated for expiry.
            backoff_service: Optional Commit #7
                LLMAgentTaskRecoveryPreflightScheduleBackoffService --
                when given, its own calculate()'s dead_letter_required
                also expires a schedule regardless of TTL.
            max_overdue_age: Defaults to DEFAULT_SCHEDULE_EXPIRATION_TTL.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._dispatch_service = dispatch_service
        self._backoff_service = backoff_service
        self._max_overdue_age = max_overdue_age if max_overdue_age is not None else DEFAULT_SCHEDULE_EXPIRATION_TTL

    def check(
        self, task_id: str, schedule_id: str, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleExpirationResult:
        """Read-only expiration verdict for task_id's exact schedule_id,
        re-evaluated fresh every call.

        Raises:
            InvalidAgentTaskRecoveryScheduleExpirationError: If task_id/
                schedule_id is not a non-empty string, now is given and
                is not a datetime, or schedule_id names no recorded
                schedule for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        now = self._resolve_now(now)

        schedule = self._scheduling_service.get(task_id, schedule_id)
        if schedule is None:
            raise InvalidAgentTaskRecoveryScheduleExpirationError(
                f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
            )

        if schedule.status == CANCELLED:
            return self._result(task_id, schedule_id, NOT_APPLICABLE, None, "schedule has already been cancelled", now)
        if schedule.status == INVALIDATED:
            return self._result(
                task_id, schedule_id, NOT_APPLICABLE, None, "schedule is not currently authorized", now
            )
        dispatched = False
        if self._dispatch_service is not None:
            dispatched = any(d.schedule_id == schedule_id for d in self._dispatch_service.list(task_id))
        if dispatched:
            return self._result(
                task_id, schedule_id, NOT_APPLICABLE, None, "schedule has already been dispatched", now
            )

        if schedule.execute_at is not None and now < schedule.execute_at:
            return self._result(
                task_id, schedule_id, NOT_YET_DUE, schedule.execute_at,
                "execution window has not been reached yet", now,
            )

        if self._backoff_service is not None:
            backoff_result = self._backoff_service.calculate(task_id, schedule_id, now=now)
            if backoff_result.dead_letter_required:
                return self._result(
                    task_id, schedule_id, EXPIRED, now,
                    "recovery retry attempts are exhausted per existing retry policy", now,
                )

        reference = schedule.execute_at if schedule.execute_at is not None else schedule.created_at
        ttl_deadline = reference + self._max_overdue_age
        if now >= ttl_deadline:
            return self._result(
                task_id, schedule_id, EXPIRED, ttl_deadline,
                f"schedule has been due since {reference.isoformat()} and exceeded its "
                f"{self._max_overdue_age} expiration window",
                now,
            )
        return self._result(
            task_id, schedule_id, DUE, ttl_deadline, "schedule is due and still within its expiration window", now
        )

    def expire(
        self, task_id: str, schedule_id: str, reason: Optional[str] = None, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryPreflightSchedule:
        """Expire task_id's exact schedule_id, if currently eligible.
        Idempotent: a schedule already cancelled, invalidated, or
        dispatched is returned unchanged, no-op.

        Raises:
            InvalidAgentTaskRecoveryScheduleExpirationError: If task_id/
                schedule_id is not a non-empty string, now is given and
                is not a datetime, schedule_id names no recorded schedule
                for task_id, or the schedule is not yet eligible for
                expiration (not yet due, or due but still within its
                expiration window)
        """
        now = self._resolve_now(now)
        result = self.check(task_id, schedule_id, now=now)

        if result.state == NOT_APPLICABLE:
            return self._scheduling_service.get(task_id, schedule_id)

        if not result.expired:
            raise InvalidAgentTaskRecoveryScheduleExpirationError(
                f"schedule {schedule_id!r} is not yet eligible for expiration: {result.reason}"
            )

        expire_reason = _EXPIRATION_REASON_PREFIX + (reason if reason is not None else result.reason)
        return self._scheduling_service.cancel(task_id, schedule_id, reason=expire_reason)

    def expire_due(self, task_id: str, now: Optional[datetime] = None) -> AgentTaskRecoveryScheduleReconciliationResult:
        """Expire every one of task_id's own schedules currently eligible
        for expiration -- schedules that are not yet due, already
        cancelled/invalidated/dispatched, or due but still within their
        own expiration window are left completely untouched.

        Raises:
            InvalidAgentTaskRecoveryScheduleExpirationError: If task_id
                is not a non-empty string, or now is given and is not a
                datetime
        """
        self._require_text(task_id, "task_id")
        now = self._resolve_now(now)

        affected = []
        for schedule in self._scheduling_service.list(task_id):
            if schedule.status != SCHEDULED:
                continue
            result = self.check(task_id, schedule.schedule_id, now=now)
            if not result.expired:
                continue
            expired_record = self.expire(task_id, schedule.schedule_id, now=now)
            affected.append(
                AgentTaskRecoveryScheduleReconciliationEntry(
                    schedule_id=schedule.schedule_id, preflight_id=schedule.preflight_id,
                    previous_status=schedule.status, new_status=expired_record.status, reason=result.reason,
                )
            )

        return AgentTaskRecoveryScheduleReconciliationResult(task_id=task_id, affected=tuple(affected), reconciled_at=now)

    def _result(self, task_id, schedule_id, state, deadline, reason, now):
        return AgentTaskRecoveryScheduleExpirationResult(
            task_id=task_id, schedule_id=schedule_id, state=state, expired=(state == EXPIRED),
            deadline=deadline, reason=reason, checked_at=now,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleExpirationError(
                f"{field_name} is required and must be a non-empty string"
            )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleExpirationError("now must be a datetime when given")
        return now
