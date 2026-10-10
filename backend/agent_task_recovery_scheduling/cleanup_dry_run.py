from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .cleanup import LLMAgentTaskRecoveryPreflightScheduleCleanupService
from .cleanup_idempotency import CLEANUP_ELIGIBLE, LLMAgentTaskRecoveryPreflightScheduleCleanupIdempotencyService
from .dispatch import LLMAgentTaskRecoveryPreflightScheduleDispatchService
from .service import LLMAgentTaskRecoveryPreflightSchedulingService


class InvalidAgentTaskRecoveryScheduleCleanupDryRunError(ValueError):
    """Raised when dry_run() is given invalid arguments."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCleanupPlan:
    """dry_run()'s read-only forecast of one cleanup pass, in the
    scheduling service's own oldest-to-newest order. `candidates` are
    (schedule_id, terminal reason) pairs -- exactly what cleanup() would
    clean; `skipped` are (schedule_id, state) pairs for everything it
    would leave untouched (already_cleaned, still_active, dispatched);
    `failures` are (schedule_id, error) pairs for schedules whose
    evaluation raised, the same way cleanup() would record them."""

    task_id: str
    planned_at: datetime
    candidates: tuple
    skipped: tuple
    failures: tuple
    candidate_count: int
    skipped_count: int


class LLMAgentTaskRecoveryPreflightScheduleCleanupDryRunService:
    """Previews what cleanup() would do -- never a second copy of its
    rules: each schedule is classified by the idempotency service's own
    check(), which in turn asks the cleanup service's own read-only
    terminal_reason(), the very decision cleanup() itself acts on. So a
    plan and a real cleanup pass at the same `now` cannot disagree.

    Writes nothing (no cancel, no expire, no reconcile), so it is
    trivially idempotent and deterministic: the same schedules and `now`
    always yield an equal plan.
    """

    def __init__(
        self,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        dispatch_service: LLMAgentTaskRecoveryPreflightScheduleDispatchService = None,
        cleanup_service: LLMAgentTaskRecoveryPreflightScheduleCleanupService = None,
        idempotency_service: LLMAgentTaskRecoveryPreflightScheduleCleanupIdempotencyService = None,
    ):
        """
        Args:
            scheduling_service: Defaults to a fresh service, shared with
                any defaulted collaborator so all see the same records.
            cleanup_service/idempotency_service: Default to ones built
                over the same scheduling_service/dispatch_service.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        if idempotency_service is None:
            idempotency_service = LLMAgentTaskRecoveryPreflightScheduleCleanupIdempotencyService(
                scheduling_service=self._scheduling_service, dispatch_service=dispatch_service,
                cleanup_service=cleanup_service,
            )
        self._idempotency_service = idempotency_service

    def dry_run(self, task_id: str, now: Optional[datetime] = None) -> AgentTaskRecoveryScheduleCleanupPlan:
        """
        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupDryRunError: If
                task_id is not a non-empty string, or now is given and
                is not a datetime
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryScheduleCleanupDryRunError(
                "task_id is required and must be a non-empty string"
            )
        if now is None:
            now = datetime.now(timezone.utc)
        elif not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleCleanupDryRunError("now must be a datetime when given")

        candidates: list = []
        skipped: list = []
        failures: list = []
        for schedule in self._scheduling_service.list(task_id):
            try:
                verdict = self._idempotency_service.check(task_id, schedule.schedule_id, now=now)
            except Exception as error:
                failures.append((schedule.schedule_id, str(error)))
                continue
            if verdict.state == CLEANUP_ELIGIBLE:
                candidates.append((schedule.schedule_id, verdict.reason))
            else:
                skipped.append((schedule.schedule_id, verdict.state))

        return AgentTaskRecoveryScheduleCleanupPlan(
            task_id=task_id, planned_at=now, candidates=tuple(candidates), skipped=tuple(skipped),
            failures=tuple(failures), candidate_count=len(candidates), skipped_count=len(skipped),
        )
