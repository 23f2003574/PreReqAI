from dataclasses import dataclass
from datetime import datetime

from .cleanup import AgentTaskRecoveryScheduleCleanupResult


class InvalidAgentTaskRecoveryScheduleCleanupReportingError(ValueError):
    """Raised when report() is given invalid arguments, or a cleanup
    result that belongs to a different task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCleanupReport:
    """report()'s read-only view of one cleanup pass, copied verbatim from
    the cleanup result: `reason_counts` is a tuple of (reason, count)
    pairs sorted by reason (deterministic, and hashable/comparable
    unlike a dict), `failures` a tuple of (schedule_id, error) pairs."""

    task_id: str
    cleaned_at: datetime
    cleaned_count: int
    skipped_count: int
    failure_count: int
    cleaned_schedule_ids: tuple
    skipped_schedule_ids: tuple
    reason_counts: tuple
    failures: tuple


class LLMAgentTaskRecoveryPreflightScheduleCleanupReportingService:
    """Summarizes a cleanup pass -- never recomputes it: every field is
    read straight from the given AgentTaskRecoveryScheduleCleanupResult
    (IDs and reasons in the order the cleanup itself recorded them),
    and nothing here touches any schedule, store or clock. The same
    result always yields an equal report."""

    def report(
        self, task_id: str, cleanup_result: AgentTaskRecoveryScheduleCleanupResult
    ) -> AgentTaskRecoveryScheduleCleanupReport:
        """
        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupReportingError: If
                task_id is not a non-empty string, cleanup_result is not
                a cleanup result, or it was produced for another task_id
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryScheduleCleanupReportingError(
                "task_id is required and must be a non-empty string"
            )
        if not isinstance(cleanup_result, AgentTaskRecoveryScheduleCleanupResult):
            raise InvalidAgentTaskRecoveryScheduleCleanupReportingError(
                "cleanup_result must be an AgentTaskRecoveryScheduleCleanupResult"
            )
        if cleanup_result.task_id != task_id:
            raise InvalidAgentTaskRecoveryScheduleCleanupReportingError(
                f"cleanup_result belongs to task_id {cleanup_result.task_id!r}, not {task_id!r}"
            )

        counts: dict = {}
        for _, reason in cleanup_result.cleaned_reasons:
            counts[reason] = counts.get(reason, 0) + 1

        return AgentTaskRecoveryScheduleCleanupReport(
            task_id=task_id, cleaned_at=cleanup_result.cleaned_at,
            cleaned_count=cleanup_result.cleaned_count, skipped_count=cleanup_result.skipped_count,
            failure_count=len(cleanup_result.failures),
            cleaned_schedule_ids=cleanup_result.cleaned_schedule_ids,
            skipped_schedule_ids=cleanup_result.skipped_schedule_ids,
            reason_counts=tuple(sorted(counts.items())), failures=cleanup_result.failures,
        )
