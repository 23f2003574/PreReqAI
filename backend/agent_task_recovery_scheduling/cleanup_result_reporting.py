from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .cleanup_result import LLMAgentTaskRecoveryPreflightScheduleCleanupResultService


class InvalidAgentTaskRecoveryScheduleCleanupResultReportingError(ValueError):
    """Raised when report() is given invalid arguments, task_id has no
    recorded cleanup result, or result_id names none for task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCleanupResultReport:
    """report()'s read-only view of one PERSISTED batch cleanup result.

    `is_current` distinguishes the two cases: True when the reported
    result is task_id's most recent one, False when it is a historical
    one (then `current_result_id` names the latest). `entries` are the
    recorded per-schedule outcomes verbatim and `failure_summary` the
    (schedule_id, error) pairs of the failed ones, both in processing
    order. `historical_results` are (result_id, executed_at) references
    to every OTHER recorded result for the task, oldest run first."""

    task_id: str
    result_id: str
    executed_at: datetime
    recorded_at: datetime
    is_current: bool
    current_result_id: str
    total_processed: int
    cleaned_count: int
    skipped_count: int
    failed_count: int
    entries: tuple
    failure_summary: tuple
    historical_results: tuple


class LLMAgentTaskRecoveryPreflightScheduleCleanupResultReportingService:
    """Summarizes an already-persisted batch cleanup result -- never
    reruns cleanup and never recomputes anything: every field is read
    from the #9 result service's own record (its get()/history()), so
    the same stored results always yield an equal report, and nothing
    here writes."""

    def __init__(self, result_service: LLMAgentTaskRecoveryPreflightScheduleCleanupResultService = None):
        self._result_service = (
            result_service if result_service is not None else LLMAgentTaskRecoveryPreflightScheduleCleanupResultService()
        )

    def report(self, task_id: str, result_id: Optional[str] = None) -> AgentTaskRecoveryScheduleCleanupResultReport:
        """Report task_id's result_id, or its most recent result when
        result_id is omitted.

        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupResultReportingError:
                If task_id is not a non-empty string, result_id is given
                and is not a non-empty string, task_id has no recorded
                result, or result_id names none for task_id
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryScheduleCleanupResultReportingError(
                "task_id is required and must be a non-empty string"
            )
        if result_id is not None and (not result_id or not isinstance(result_id, str)):
            raise InvalidAgentTaskRecoveryScheduleCleanupResultReportingError(
                "result_id must be a non-empty string when given"
            )

        history = self._result_service.history(task_id)
        if not history:
            raise InvalidAgentTaskRecoveryScheduleCleanupResultReportingError(
                f"no cleanup result is recorded for task_id {task_id!r}"
            )
        current = history[-1]
        record = current if result_id is None else next((r for r in history if r.result_id == result_id), None)
        if record is None:
            raise InvalidAgentTaskRecoveryScheduleCleanupResultReportingError(
                f"no cleanup result {result_id!r} is recorded for task_id {task_id!r}"
            )

        return AgentTaskRecoveryScheduleCleanupResultReport(
            task_id=task_id, result_id=record.result_id, executed_at=record.executed_at,
            recorded_at=record.recorded_at, is_current=record.result_id == current.result_id,
            current_result_id=current.result_id, total_processed=len(record.entries),
            cleaned_count=record.cleaned_count, skipped_count=record.skipped_count,
            failed_count=record.failed_count, entries=record.entries,
            failure_summary=tuple((e.schedule_id, e.error) for e in record.entries if e.error is not None),
            historical_results=tuple((r.result_id, r.executed_at) for r in history if r.result_id != record.result_id),
        )
