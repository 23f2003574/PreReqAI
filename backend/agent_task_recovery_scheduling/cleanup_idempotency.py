from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .cleanup import LLMAgentTaskRecoveryPreflightScheduleCleanupService
from .dispatch import DISPATCHED, LLMAgentTaskRecoveryPreflightScheduleDispatchService
from .models import CANCELLED
from .service import LLMAgentTaskRecoveryPreflightSchedulingService

ALREADY_CLEANED = "already_cleaned"
CLEANUP_ELIGIBLE = "cleanup_eligible"
STILL_ACTIVE = "still_active"


class InvalidAgentTaskRecoveryScheduleCleanupIdempotencyError(ValueError):
    """Raised when check() is given invalid arguments, or names a
    schedule that does not exist for task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCleanupIdempotencyResult:
    """check()'s read-only verdict, re-derived fresh on every call.
    `state` is ALREADY_CLEANED, CLEANUP_ELIGIBLE, STILL_ACTIVE, or
    DISPATCHED (completed/consumed -- cleanup never touches it).

    `reason` is the terminal reason cleanup would apply when
    CLEANUP_ELIGIBLE, or the stored cancellation_reason when
    ALREADY_CLEANED (None if none was recorded); `cleaned_at` is the
    stored cancelled_at, so `history_recorded` False marks a cancelled
    schedule whose own history is missing."""

    task_id: str
    schedule_id: str
    state: str
    reason: Optional[str]
    cleaned_at: Optional[datetime]
    history_recorded: bool
    checked_at: datetime


class LLMAgentTaskRecoveryPreflightScheduleCleanupIdempotencyService:
    """Says whether cleanup has already been applied to a schedule --
    never a second record of it: the stored schedule's own CANCELLED
    status, cancelled_at and cancellation_reason ARE the cleanup
    history (cleanup only ever ends in the scheduling service's own
    idempotent cancel(), which keeps the first reason/timestamp
    standing), and eligibility is the cleanup service's own read-only
    terminal_reason(), so this can never disagree with what cleanup()
    would do.

    That is also why repeated cleanup is safe: a cleaned schedule reads
    ALREADY_CLEANED, cleanup() skips it, and its stored cancelled_at/
    reason never change on any later pass. An active schedule reads
    STILL_ACTIVE and is never modified. Writes nothing and never
    executes recovery.
    """

    def __init__(
        self,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        dispatch_service: LLMAgentTaskRecoveryPreflightScheduleDispatchService = None,
        cleanup_service: LLMAgentTaskRecoveryPreflightScheduleCleanupService = None,
    ):
        """
        Args:
            scheduling_service: Defaults to a fresh service, and is
                shared with a defaulted cleanup_service.
            dispatch_service: Optional; dispatched schedules read
                DISPATCHED.
            cleanup_service: Defaults to one built over the same
                scheduling_service/dispatch_service.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._dispatch_service = dispatch_service
        self._cleanup_service = (
            cleanup_service
            if cleanup_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleCleanupService(
                scheduling_service=self._scheduling_service, dispatch_service=dispatch_service
            )
        )

    def check(
        self, task_id: str, schedule_id: str, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleCleanupIdempotencyResult:
        """
        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupIdempotencyError: If
                task_id/schedule_id is not a non-empty string, now is
                given and is not a datetime, or schedule_id names no
                recorded schedule for task_id
        """
        for value, name in ((task_id, "task_id"), (schedule_id, "schedule_id")):
            if not value or not isinstance(value, str):
                raise InvalidAgentTaskRecoveryScheduleCleanupIdempotencyError(
                    f"{name} is required and must be a non-empty string"
                )
        if now is None:
            now = datetime.now(timezone.utc)
        elif not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleCleanupIdempotencyError("now must be a datetime when given")

        schedule = self._scheduling_service.get(task_id, schedule_id)
        if schedule is None:
            raise InvalidAgentTaskRecoveryScheduleCleanupIdempotencyError(
                f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
            )

        def result(state, reason=None):
            return AgentTaskRecoveryScheduleCleanupIdempotencyResult(
                task_id=task_id, schedule_id=schedule_id, state=state, reason=reason,
                cleaned_at=schedule.cancelled_at,
                history_recorded=schedule.cancelled_at is not None and schedule.cancellation_reason is not None,
                checked_at=now,
            )

        if schedule.status == CANCELLED:
            return result(ALREADY_CLEANED, schedule.cancellation_reason)
        if self._dispatch_service is not None and any(
            d.schedule_id == schedule_id for d in self._dispatch_service.list(task_id)
        ):
            return result(DISPATCHED)
        reason = self._cleanup_service.terminal_reason(task_id, schedule, now=now)
        return result(CLEANUP_ELIGIBLE, reason) if reason is not None else result(STILL_ACTIVE)
