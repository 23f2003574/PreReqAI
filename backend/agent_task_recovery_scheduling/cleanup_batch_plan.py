from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .cleanup_candidates import LLMAgentTaskRecoveryPreflightScheduleCleanupCandidateService
from .cleanup_ordering import LLMAgentTaskRecoveryPreflightScheduleCleanupOrderingService


class InvalidAgentTaskRecoveryScheduleCleanupBatchPlanError(ValueError):
    """Raised when plan() is given invalid arguments."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCleanupBatchPlan:
    """plan()'s read-only batch: `schedule_ids` in the ordering
    service's processing order, `reasons` the matching (schedule_id,
    terminal reason) pairs in that same order, `count` their number."""

    task_id: str
    planned_at: datetime
    schedule_ids: tuple
    reasons: tuple
    count: int


class LLMAgentTaskRecoveryPreflightScheduleCleanupBatchPlanService:
    """Builds the ordered batch a cleanup run would process -- never a
    second cleanup framework and never a second copy of its rules:
    candidates come from the candidate service (whose eligibility is the
    cleanup service's own terminal_reason(), the same decision a real
    cleanup pass acts on) and are ordered by the ordering service, so
    the batch holds exactly the schedules real cleanup would clean.

    Writes nothing and never executes recovery, so repeated plans over
    unchanged schedules are equal.
    """

    def __init__(
        self,
        candidate_service: LLMAgentTaskRecoveryPreflightScheduleCleanupCandidateService = None,
        ordering_service: LLMAgentTaskRecoveryPreflightScheduleCleanupOrderingService = None,
    ):
        """
        Args:
            candidate_service: Defaults to a fresh service.
            ordering_service: Defaults to one over the same
                candidate_service.
        """
        self._candidate_service = (
            candidate_service
            if candidate_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleCleanupCandidateService()
        )
        self._ordering_service = (
            ordering_service
            if ordering_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleCleanupOrderingService(
                candidate_service=self._candidate_service
            )
        )

    def plan(self, task_id: str, now: Optional[datetime] = None) -> AgentTaskRecoveryScheduleCleanupBatchPlan:
        """
        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupBatchPlanError: If
                task_id is not a non-empty string, or now is given and
                is not a datetime
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryScheduleCleanupBatchPlanError(
                "task_id is required and must be a non-empty string"
            )
        if now is None:
            now = datetime.now(timezone.utc)
        elif not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleCleanupBatchPlanError("now must be a datetime when given")

        candidates = self._candidate_service.find(task_id, now=now)
        ordered = self._ordering_service.order(task_id, candidates, now=now)
        return AgentTaskRecoveryScheduleCleanupBatchPlan(
            task_id=task_id, planned_at=now,
            schedule_ids=tuple(c.schedule_id for c in ordered),
            reasons=tuple((c.schedule_id, c.reason) for c in ordered),
            count=len(ordered),
        )
