from dataclasses import dataclass
from datetime import datetime, timezone

from backend.agent_task_recovery_guardrails import LLMAgentTaskRecoveryPreflightAuthorizationValidationService

from .dispatch import LLMAgentTaskRecoveryPreflightScheduleDispatchService
from .models import CANCELLED, INVALIDATED, SCHEDULED
from .service import LLMAgentTaskRecoveryPreflightSchedulingService


class InvalidAgentTaskRecoveryScheduleReconciliationError(ValueError):
    """Raised when reconcile()/reconcile_all() is given invalid
    arguments."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleReconciliationEntry:
    """One schedule reconciliation actually acted on this call --
    unaffected (already-cancelled, already-dispatched, or still genuinely
    valid) schedules never produce an entry at all (Rule: "Preserve valid
    actionable schedules unchanged")."""

    schedule_id: str
    preflight_id: str
    previous_status: str
    new_status: str
    reason: str


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleReconciliationResult:
    """LLMAgentTaskRecoveryPreflightScheduleReconciliationService's
    complete report of one reconciliation pass."""

    task_id: str
    affected: tuple
    reconciled_at: datetime


class LLMAgentTaskRecoveryPreflightScheduleReconciliationService:
    """Cancels any persisted Commit #1 schedule that can no longer
    actually be trusted -- never a second scheduling/state-management
    system (Rule: "Do not create duplicate scheduling or state-
    management infrastructure"): every eligibility fact here is read
    straight from Commit #1's own `list()` (whose own effective status
    already re-checks Commit #10-of-agent_task_recovery_guardrails'
    authorization validation internally -- stale/invalidated/superseded/
    revoked/policy-blocked, all reused, none re-derived) and, when a
    schedule needs to be acted on, the ONLY write anywhere in this class
    is Commit #1's own already-idempotent `cancel()`.

    Deliberately does NOT reuse Commit #2's own schedule validation
    service for the invalidity check: that service also flags a schedule
    whose execution window has not yet arrived as "not valid" -- exactly
    the wrong signal for reconciliation, which must never cancel a
    schedule merely because it is not YET due (Rule: "Preserve valid
    actionable schedules unchanged"). Commit #1's own effective status
    (SCHEDULED vs INVALIDATED) already excludes the window concern
    entirely, which is exactly the right, narrower check to reuse here.

    Detects duplicate ACTIVE schedules for the same preflight_id (a
    genuinely new check, since nothing else in this series looks across
    a task's own multiple schedules at once) by keeping only the
    earliest-created SCHEDULED one per preflight_id and cancelling any
    later one found for the identical preflight_id.

    Already-dispatched schedules (Rule: "cancelled or already-dispatched
    schedules") are left completely alone when an optional
    `dispatch_service` is supplied -- cancelling something already handed
    off to the real queue would be meaningless and is explicitly out of
    scope (Rule: "Never execute recovery" -- and never un-dispatch one
    either).

    Idempotent (Rule): cancel() itself is already idempotent by schedule_id
    (Commit #1), so calling reconcile_all() repeatedly with nothing else
    changed produces zero NEW `affected` entries on the second call.

    Never deletes history (Rule): every schedule ever created remains
    retrievable via Commit #1's own list()/get() forever -- reconciliation
    only ever transitions a record's own status via the same
    dataclasses.replace()-not-mutate discipline cancel() already uses.
    """

    def __init__(
        self,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        authorization_validation_service: LLMAgentTaskRecoveryPreflightAuthorizationValidationService = None,
        dispatch_service: LLMAgentTaskRecoveryPreflightScheduleDispatchService = None,
    ):
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._authorization_validation_service = (
            authorization_validation_service
            if authorization_validation_service is not None
            else LLMAgentTaskRecoveryPreflightAuthorizationValidationService()
        )
        self._dispatch_service = dispatch_service

    def reconcile(self, task_id: str, schedule_id: str = None) -> AgentTaskRecoveryScheduleReconciliationResult:
        """Reconcile task_id's exact schedule_id, or every one of
        task_id's own schedules when schedule_id is omitted (delegates
        directly to reconcile_all()).

        Raises:
            InvalidAgentTaskRecoveryScheduleReconciliationError: If
                task_id is not a non-empty string, or schedule_id is
                given and is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        if schedule_id is None:
            return self.reconcile_all(task_id)

        self._require_text(schedule_id, "schedule_id")
        schedules = [s for s in self._scheduling_service.list(task_id) if s.schedule_id == schedule_id]
        return self._run(task_id, schedules)

    def reconcile_all(self, task_id: str) -> AgentTaskRecoveryScheduleReconciliationResult:
        """Reconcile every schedule ever recorded for task_id.

        Raises:
            InvalidAgentTaskRecoveryScheduleReconciliationError: If
                task_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        return self._run(task_id, self._scheduling_service.list(task_id))

    def _run(self, task_id: str, schedules: list) -> AgentTaskRecoveryScheduleReconciliationResult:
        dispatched_schedule_ids = set()
        if self._dispatch_service is not None:
            dispatched_schedule_ids = {d.schedule_id for d in self._dispatch_service.list(task_id)}

        affected: list = []
        seen_preflight_ids: set = set()

        for schedule in schedules:
            if schedule.status == CANCELLED or schedule.schedule_id in dispatched_schedule_ids:
                continue

            if schedule.preflight_id in seen_preflight_ids:
                entry = self._cancel_and_report(task_id, schedule, "duplicate active schedule for this preflight_id")
                if entry is not None:
                    affected.append(entry)
                continue
            seen_preflight_ids.add(schedule.preflight_id)

            if schedule.status == INVALIDATED:
                validation = self._authorization_validation_service.validate(task_id, schedule.authorization_id)
                reason = "; ".join(validation.blocking_reasons) or "authorization is no longer valid"
                entry = self._cancel_and_report(task_id, schedule, reason)
                if entry is not None:
                    affected.append(entry)

        return AgentTaskRecoveryScheduleReconciliationResult(
            task_id=task_id, affected=tuple(affected), reconciled_at=datetime.now(timezone.utc)
        )

    def _cancel_and_report(self, task_id: str, schedule, reason: str):
        cancelled = self._scheduling_service.cancel(task_id, schedule.schedule_id, reason=reason)
        if cancelled.status != CANCELLED or schedule.status == CANCELLED:
            return None
        return AgentTaskRecoveryScheduleReconciliationEntry(
            schedule_id=schedule.schedule_id, preflight_id=schedule.preflight_id,
            previous_status=schedule.status, new_status=CANCELLED, reason=reason,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleReconciliationError(
                f"{field_name} is required and must be a non-empty string"
            )
