from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend.agent_task_recovery_guardrails import LLMAgentTaskRecoveryPreflightAuthorizationValidationService

from .dispatch import LLMAgentTaskRecoveryPreflightScheduleDispatchService
from .expiration import LLMAgentTaskRecoveryPreflightScheduleExpirationService
from .models import CANCELLED, INVALIDATED
from .reconciliation import LLMAgentTaskRecoveryPreflightScheduleReconciliationService
from .service import LLMAgentTaskRecoveryPreflightSchedulingService


EXPIRED_REASON = "expired"
INVALIDATED_REASON = "invalidated"


class InvalidAgentTaskRecoveryScheduleCleanupError(ValueError):
    """Raised when cleanup() is given invalid arguments."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCleanupResult:
    """One cleanup() pass -- how many of task_id's own schedules were
    actually moved to their persisted terminal form (cleaned) versus
    left exactly as they were (skipped), and which schedule_ids fell in
    each bucket. Every schedule ever recorded for task_id lands in
    exactly one of cleaned, skipped, or failures.

    cleaned_reasons pairs each cleaned schedule_id with the terminal
    reason it was cleaned for (EXPIRED_REASON or INVALIDATED_REASON), in
    cleaned order; failures pairs a schedule_id with the error text of a
    cleanup attempt that raised (that one schedule is left as it was and
    the pass continues)."""

    task_id: str
    cleaned_count: int
    skipped_count: int
    cleaned_schedule_ids: tuple
    skipped_schedule_ids: tuple
    cleaned_at: datetime
    cleaned_reasons: tuple = ()
    failures: tuple = ()


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

        dispatched_ids = self._dispatched_ids(task_id)

        cleaned: list = []
        skipped: list = []
        reasons: list = []
        failures: list = []
        for schedule in self._scheduling_service.list(task_id):
            schedule_id = schedule.schedule_id
            try:
                reason = self._clean(task_id, schedule, dispatched_ids, now)
            except Exception as error:
                failures.append((schedule_id, str(error)))
                continue
            if reason is None:
                skipped.append(schedule_id)
            else:
                cleaned.append(schedule_id)
                reasons.append((schedule_id, reason))

        return AgentTaskRecoveryScheduleCleanupResult(
            task_id=task_id, cleaned_count=len(cleaned), skipped_count=len(skipped),
            cleaned_schedule_ids=tuple(cleaned), skipped_schedule_ids=tuple(skipped), cleaned_at=now,
            cleaned_reasons=tuple(reasons), failures=tuple(failures),
        )

    def terminal_reason(self, task_id: str, schedule, now: Optional[datetime] = None) -> Optional[str]:
        """Read-only: the terminal reason cleanup() would clean schedule
        (one of task_id's own, as returned by the scheduling service's
        list()/get()) for right now, or None when cleanup() would leave
        it untouched. Never writes."""
        return self._terminal_reason(
            task_id, schedule, self._dispatched_ids(task_id), now or datetime.now(timezone.utc)
        )

    def _dispatched_ids(self, task_id: str) -> set:
        if self._dispatch_service is None:
            return set()
        return {d.schedule_id for d in self._dispatch_service.list(task_id)}

    def _terminal_reason(self, task_id: str, schedule, dispatched_ids: set, now: datetime) -> Optional[str]:
        if schedule.schedule_id in dispatched_ids or schedule.status == CANCELLED:
            return None
        if schedule.status == INVALIDATED:
            return INVALIDATED_REASON
        if self._expiration_service.check(task_id, schedule.schedule_id, now=now).expired:
            return EXPIRED_REASON
        return None

    def _clean(self, task_id: str, schedule, dispatched_ids: set, now: datetime) -> Optional[str]:
        """The terminal reason schedule was just cleaned for, or None
        when it was left untouched."""
        reason = self._terminal_reason(task_id, schedule, dispatched_ids, now)
        if reason == INVALIDATED_REASON:
            result = self._reconciliation_service.reconcile(task_id, schedule.schedule_id)
            return reason if result.affected else None
        if reason == EXPIRED_REASON:
            self._expiration_service.expire(task_id, schedule.schedule_id, now=now)
        return reason
