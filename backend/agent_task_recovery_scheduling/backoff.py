from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.agent_task_queue_retry_scheduler import LLMAgentTaskRetryScheduler

from .models import CANCELLED, INVALIDATED, AgentTaskRecoveryPreflightSchedule
from .service import LLMAgentTaskRecoveryPreflightSchedulingService


class InvalidAgentTaskRecoveryScheduleBackoffError(ValueError):
    """Raised when calculate()/reschedule() is given invalid arguments,
    or reschedule() is asked to act on a schedule that is cancelled,
    invalidated, superseded, or otherwise not currently eligible for
    another retry attempt."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleBackoffResult:
    """calculate()'s read-only, explainable verdict -- re-derived fresh
    on every call from Commit #9(-of-agent_task_queue)'s own retry
    eligibility/backoff state, never cached or persisted."""

    task_id: str
    schedule_id: str
    eligible: bool
    attempt: Optional[int]
    remaining_attempts: Optional[int]
    delay: Optional[timedelta]
    execute_at: Optional[datetime]
    dead_letter_required: bool
    blocking_reasons: tuple
    factors: tuple
    calculated_at: datetime


class LLMAgentTaskRecoveryPreflightScheduleBackoffService:
    """Deterministic backoff for scheduled recovery attempts -- never a
    second retry engine (Rule: "Do not invent a new retry engine"): the
    ONLY source of delay/attempt/limit logic anywhere in this class is
    backend.agent_task_queue_retry_scheduler.LLMAgentTaskRetryScheduler's
    own resolve_eligibility(), which itself already reuses Commit #9(-of-
    agent_task_queue)'s own LLMAgentTaskQueueRetryEligibilityService --
    max_attempts, dead-letter state, and current readiness/policy
    (deadlines and budgets already enforced there) are all read from that
    one existing chain, never re-derived here.

    Never bypasses guardrails (Rule: "Never reschedule cancelled,
    invalidated, superseded, or unauthorized recovery work"): calculate()
    always checks Commit #1's own EFFECTIVE schedule status first (which
    itself already folds in Commit #10-of-agent_task_recovery_guardrails'
    own authorization validation) -- a cancelled, invalidated, or
    superseded (cancelled by Commit #4's own reconciliation) schedule is
    reported ineligible before any retry-policy factor is even consulted.

    calculate() is deterministic (Rule) for a fixed `now`: it performs no
    writes and calls resolve_eligibility() exactly once, a pure read.

    reschedule() only ever updates SCHEDULING state (Rule: "must update
    scheduling state only; never execute recovery"): it never calls
    anything from agent_task_event_analytics' own execution service or
    Commit #11-of-agent_task_recovery_guardrails' own consumption service.
    It reuses Commit #1's own cancel() + schedule() rather than mutating a
    stored record in place -- Commit #1's own store already keeps every
    schedule_id it has ever seen (Rule: "Preserve previous schedule/
    history records rather than silently overwriting them"): the old
    schedule is left, cancelled, in that history, and a new schedule_id is
    created for the recalculated execute_at.
    """

    def __init__(
        self,
        retry_scheduler: LLMAgentTaskRetryScheduler,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
    ):
        """
        Args:
            retry_scheduler: The exact backend.agent_task_queue_retry_
                scheduler.LLMAgentTaskRetryScheduler instance wired to
                task_id's own retry/attempt/backoff metadata -- required,
                never defaulted (mirrors that scheduler's own
                eligibility_service being required rather than guessed).
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService.
        """
        if retry_scheduler is None:
            raise InvalidAgentTaskRecoveryScheduleBackoffError("retry_scheduler is required")
        self._retry_scheduler = retry_scheduler
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )

    def calculate(
        self, task_id: str, schedule_id: str, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleBackoffResult:
        """Read-only backoff calculation for task_id's exact schedule_id,
        re-derived fresh every call.

        Raises:
            InvalidAgentTaskRecoveryScheduleBackoffError: If task_id/
                schedule_id is not a non-empty string, or now is given
                and is not a datetime
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        now = self._resolve_now(now)

        schedule = self._scheduling_service.get(task_id, schedule_id)
        blocking_reasons = []
        if schedule is None:
            blocking_reasons.append(f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}")
        elif schedule.status == CANCELLED:
            blocking_reasons.append("schedule has been cancelled or superseded")
        elif schedule.status == INVALIDATED:
            blocking_reasons.append("schedule is no longer authorized")

        eligibility = self._retry_scheduler.resolve_eligibility(task_id, now=now)
        factors = (
            f"attempt_count={eligibility.attempt_count}",
            f"remaining_attempts={eligibility.remaining_attempts}",
            f"policy_reason={eligibility.reason}",
            f"dead_letter_required={eligibility.dead_letter_required}",
        )
        if eligibility.dead_letter_required:
            blocking_reasons.append("retry attempts are exhausted and this task requires dead-lettering")
        elif not eligibility.eligible:
            blocking_reasons.append(f"not currently eligible for another retry attempt: {eligibility.reason}")

        delay = None
        execute_at = None
        if not blocking_reasons:
            execute_at = eligibility.next_eligible_at if eligibility.next_eligible_at is not None else now
            delay = max(execute_at - now, timedelta(0))

        attempt = (eligibility.attempt_count or 0) + 1

        return AgentTaskRecoveryScheduleBackoffResult(
            task_id=task_id,
            schedule_id=schedule_id,
            eligible=not blocking_reasons,
            attempt=attempt,
            remaining_attempts=eligibility.remaining_attempts,
            delay=delay,
            execute_at=execute_at,
            dead_letter_required=eligibility.dead_letter_required,
            blocking_reasons=tuple(blocking_reasons),
            factors=factors,
            calculated_at=now,
        )

    def reschedule(
        self, task_id: str, schedule_id: str, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryPreflightSchedule:
        """Recalculate task_id's exact schedule_id's backoff and move it
        to a new execute_at -- by cancelling the old schedule_id and
        creating a new one for the same preflight_id (Commit #1's own
        cancel()/schedule()), preserving the old record in history rather
        than overwriting it in place.

        Raises:
            InvalidAgentTaskRecoveryScheduleBackoffError: If task_id/
                schedule_id is not a non-empty string, now is given and
                is not a datetime, or the schedule is not currently
                eligible for another retry attempt (cancelled,
                invalidated, superseded, unauthorized, retry-limit
                exhausted, or dead-letter required)
        """
        now = self._resolve_now(now)
        result = self.calculate(task_id, schedule_id, now=now)
        if not result.eligible:
            raise InvalidAgentTaskRecoveryScheduleBackoffError(
                f"schedule {schedule_id!r} cannot be rescheduled: " + "; ".join(result.blocking_reasons)
            )

        schedule = self._scheduling_service.get(task_id, schedule_id)
        self._scheduling_service.cancel(task_id, schedule_id, reason="superseded by recalculated backoff")
        return self._scheduling_service.schedule(task_id, schedule.preflight_id, execute_at=result.execute_at)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleBackoffError(
                f"{field_name} is required and must be a non-empty string"
            )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleBackoffError("now must be a datetime when given")
        return now
