from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .cleanup import EXPIRED_REASON, LLMAgentTaskRecoveryPreflightScheduleCleanupService
from .dispatch import LLMAgentTaskRecoveryPreflightScheduleDispatchService
from .expiration import LLMAgentTaskRecoveryPreflightScheduleExpirationService
from .service import LLMAgentTaskRecoveryPreflightSchedulingService


class InvalidAgentTaskRecoveryScheduleCleanupCandidateError(ValueError):
    """Raised when find()/is_candidate() is given invalid arguments."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCleanupCandidate:
    """One schedule the existing cleanup would clean right now. `status`
    is the schedule's current effective status (scheduled or
    invalidated), `reason` the terminal reason cleanup would apply, and
    `eligible_since` the moment it became eligible where the schedule
    records one -- the expiration deadline for an expired schedule,
    None for an invalidated one (no invalidation time is stored)."""

    task_id: str
    schedule_id: str
    preflight_id: str
    status: str
    reason: str
    created_at: datetime
    eligible_since: Optional[datetime]


class LLMAgentTaskRecoveryPreflightScheduleCleanupCandidateService:
    """Discovers cleanup candidates without cleaning any -- never a copy
    of the cleanup rules: a schedule is a candidate exactly when the
    cleanup service's own read-only terminal_reason() returns a reason
    for it, so active, not-yet-due, already-cleaned and dispatched
    schedules are excluded by the same decision cleanup() itself uses.

    Writes nothing and never executes recovery. Results are ordered by
    (created_at, schedule_id), so equal inputs give equal output.
    """

    def __init__(
        self,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        dispatch_service: LLMAgentTaskRecoveryPreflightScheduleDispatchService = None,
        expiration_service: LLMAgentTaskRecoveryPreflightScheduleExpirationService = None,
        cleanup_service: LLMAgentTaskRecoveryPreflightScheduleCleanupService = None,
    ):
        """
        Args:
            scheduling_service: Defaults to a fresh service, shared with
                every defaulted collaborator so all see the same records.
            expiration_service: Only read for an expired candidate's
                deadline; defaults to one over scheduling_service/
                dispatch_service.
            cleanup_service: Defaults to one over the same collaborators.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._expiration_service = (
            expiration_service
            if expiration_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleExpirationService(
                scheduling_service=self._scheduling_service, dispatch_service=dispatch_service
            )
        )
        self._cleanup_service = (
            cleanup_service
            if cleanup_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleCleanupService(
                scheduling_service=self._scheduling_service, dispatch_service=dispatch_service,
                expiration_service=self._expiration_service,
            )
        )

    def find(self, task_id: str, now: Optional[datetime] = None) -> tuple:
        """Every AgentTaskRecoveryScheduleCleanupCandidate for task_id.

        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupCandidateError: If
                task_id is not a non-empty string, or now is given and
                is not a datetime
        """
        self._require_text(task_id, "task_id")
        now = self._resolve_now(now)

        candidates = []
        for schedule in sorted(
            self._scheduling_service.list(task_id), key=lambda item: (item.created_at, item.schedule_id)
        ):
            reason = self._cleanup_service.terminal_reason(task_id, schedule, now=now)
            if reason is None:
                continue
            eligible_since = None
            if reason == EXPIRED_REASON:
                eligible_since = self._expiration_service.check(task_id, schedule.schedule_id, now=now).deadline
            candidates.append(
                AgentTaskRecoveryScheduleCleanupCandidate(
                    task_id=task_id, schedule_id=schedule.schedule_id, preflight_id=schedule.preflight_id,
                    status=schedule.status, reason=reason, created_at=schedule.created_at,
                    eligible_since=eligible_since,
                )
            )
        return tuple(candidates)

    def is_candidate(self, task_id: str, schedule_id: str, now: Optional[datetime] = None) -> bool:
        """Whether task_id's schedule_id is a cleanup candidate right
        now (False for an unknown schedule).

        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupCandidateError: If
                task_id/schedule_id is not a non-empty string, or now is
                given and is not a datetime
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        now = self._resolve_now(now)

        schedule = self._scheduling_service.get(task_id, schedule_id)
        if schedule is None:
            return False
        return self._cleanup_service.terminal_reason(task_id, schedule, now=now) is not None

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleCleanupCandidateError(
                f"{field_name} is required and must be a non-empty string"
            )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleCleanupCandidateError("now must be a datetime when given")
        return now
