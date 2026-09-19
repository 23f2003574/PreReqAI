from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend.agent_task_recovery_guardrails import LLMAgentTaskRecoveryPreflightAuthorizationValidationService

from .dispatch import LLMAgentTaskRecoveryPreflightScheduleDispatchService
from .expiration import LLMAgentTaskRecoveryPreflightScheduleExpirationService
from .models import CANCELLED, INVALIDATED
from .reconciliation import LLMAgentTaskRecoveryPreflightScheduleReconciliationService
from .service import LLMAgentTaskRecoveryPreflightSchedulingService


class InvalidAgentTaskRecoveryScheduleCleanupError(ValueError):
    """Raised when cleanup() is given invalid arguments."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCleanupResult:
    """One cleanup() pass -- how many of task_id's own schedules were
    actually moved to their persisted terminal form (cleaned) versus
    left exactly as they were (skipped), and which schedule_ids fell in
    each bucket. Every schedule ever recorded for task_id lands in
    exactly one of the two."""

    task_id: str
    cleaned_count: int
    skipped_count: int
    cleaned_schedule_ids: tuple
    skipped_schedule_ids: tuple
    cleaned_at: datetime


class LLMAgentTaskRecoveryPreflightScheduleCleanupService:
    """Small maintenance pass that converges obviously terminal recovery
    schedules onto their persisted terminal state -- never new scheduling
    infrastructure: the only writes are the existing expiration service's
    expire() and the existing reconciliation service's reconcile(), both
    of which end in Commit #1's own idempotent cancel().

    Only two kinds of schedule are ever cleaned:
      - EXPIRED: still SCHEDULED, but the expiration service's own
        check() reports it expired (persisted as CANCELLED "expired: ...").
      - superseded/invalidated: the scheduling service's own effective
        status reads INVALIDATED (its authorization no longer validates,
        which covers a superseded preflight); reconcile() persists it as
        CANCELLED.

    Everything else is skipped untouched: already-CANCELLED (already
    clean, whether cancelled manually or by an earlier cleanup),
    already-dispatched (completed/consumed -- there is no persisted
    "consumed" state to converge to, and un-dispatching is out of scope),
    and any active SCHEDULED one, whether not yet due, due, or still
    within its expiration window.

    Preserves history: nothing is deleted; a cleaned schedule stays
    retrievable via list()/get() with its cancellation reason.
    Idempotent: a second pass finds every cleaned schedule already
    CANCELLED and reports them all as skipped. Never executes recovery
    or reschedules.
    """

    def __init__(
        self,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        dispatch_service: LLMAgentTaskRecoveryPreflightScheduleDispatchService = None,
        expiration_service: LLMAgentTaskRecoveryPreflightScheduleExpirationService = None,
        reconciliation_service: LLMAgentTaskRecoveryPreflightScheduleReconciliationService = None,
        authorization_validation_service: LLMAgentTaskRecoveryPreflightAuthorizationValidationService = None,
    ):
        """
        Args:
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService. Also
                handed to any defaulted expiration/reconciliation
                service, so every one of them sees the same records
                (a fully-defaulted chain would otherwise each isolate
                its own scheduling state).
            dispatch_service: Optional; when given, dispatched
                schedules are skipped.
            authorization_validation_service: Optional; only used by a
                defaulted reconciliation service, for its own
                cancellation reason text.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._dispatch_service = dispatch_service
        self._expiration_service = (
            expiration_service
            if expiration_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleExpirationService(
                scheduling_service=self._scheduling_service, dispatch_service=dispatch_service
            )
        )
        self._reconciliation_service = (
            reconciliation_service
            if reconciliation_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleReconciliationService(
                scheduling_service=self._scheduling_service,
                authorization_validation_service=authorization_validation_service,
                dispatch_service=dispatch_service,
            )
        )

    def cleanup(self, task_id: str, now: Optional[datetime] = None) -> AgentTaskRecoveryScheduleCleanupResult:
        """Clean up every terminal schedule recorded for task_id.

        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupError: If task_id is
                not a non-empty string, or now is given and is not a
                datetime
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryScheduleCleanupError("task_id is required and must be a non-empty string")
        if now is None:
            now = datetime.now(timezone.utc)
        elif not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleCleanupError("now must be a datetime when given")

        dispatched_ids = set()
        if self._dispatch_service is not None:
            dispatched_ids = {d.schedule_id for d in self._dispatch_service.list(task_id)}

        cleaned: list = []
        skipped: list = []
        for schedule in self._scheduling_service.list(task_id):
            schedule_id = schedule.schedule_id
            if schedule_id in dispatched_ids or schedule.status == CANCELLED:
                skipped.append(schedule_id)
            elif schedule.status == INVALIDATED:
                result = self._reconciliation_service.reconcile(task_id, schedule_id)
                (cleaned if result.affected else skipped).append(schedule_id)
            elif self._expiration_service.check(task_id, schedule_id, now=now).expired:
                self._expiration_service.expire(task_id, schedule_id, now=now)
                cleaned.append(schedule_id)
            else:
                skipped.append(schedule_id)

        return AgentTaskRecoveryScheduleCleanupResult(
            task_id=task_id, cleaned_count=len(cleaned), skipped_count=len(skipped),
            cleaned_schedule_ids=tuple(cleaned), skipped_schedule_ids=tuple(skipped), cleaned_at=now,
        )
