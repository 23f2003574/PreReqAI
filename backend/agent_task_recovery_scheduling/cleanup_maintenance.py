from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .cleanup_candidates import LLMAgentTaskRecoveryPreflightScheduleCleanupCandidateService
from .cleanup_result import LLMAgentTaskRecoveryPreflightScheduleCleanupResultService
from .cleanup_result_reporting import LLMAgentTaskRecoveryPreflightScheduleCleanupResultReportingService
from .cleanup_result_retention import LLMAgentTaskRecoveryPreflightScheduleCleanupResultRetentionService


class InvalidAgentTaskRecoveryScheduleCleanupMaintenanceError(ValueError):
    """Raised when summarize() is given invalid arguments."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCleanupMaintenanceSummary:
    """summarize()'s one-page view of a task's cleanup maintenance,
    with CURRENT state kept apart from HISTORY:

    Current (evaluated fresh at `summarized_at`): `current_candidates`
    are the schedules cleanup would clean right now, and
    `outstanding_count` is how many of them there are -- the cleanup
    work still to do.

    Historical (persisted results only): `latest_result` is the #10
    report of the most recent persisted result, and `latest_cleaned_
    count`/`latest_skipped_count`/`latest_failed_count` its counts;
    `last_maintenance_at` is when it ran. `historical_results` are
    (result_id, executed_at) references to the older results, and
    `retention_eligible` / `retention_protected` the retention plan's
    own split of the results at or before the cutoff.

    latest_result, its counts and last_maintenance_at are None -- never
    0 -- when the task has no persisted result: "never ran" is not the
    same fact as "ran and did nothing"."""

    task_id: str
    summarized_at: datetime
    current_candidates: tuple
    outstanding_count: int
    latest_result: Optional[object]
    latest_cleaned_count: Optional[int]
    latest_skipped_count: Optional[int]
    latest_failed_count: Optional[int]
    last_maintenance_at: Optional[datetime]
    historical_results: tuple
    retention_eligible: tuple
    retention_protected: tuple


class LLMAgentTaskRecoveryPreflightScheduleCleanupMaintenanceService:
    """Combines the day's cleanup pieces into one read-only summary --
    never another subsystem and never any cleanup logic of its own:
    candidates come from the #5 candidate service, the latest result and
    history references from the #10 reporting service, and the retention
    split from the #12 retention service's plan(). It never runs
    cleanup, applies retention or writes anything, so the same schedules,
    results and `now` always yield an equal summary.
    """

    def __init__(
        self,
        candidate_service: LLMAgentTaskRecoveryPreflightScheduleCleanupCandidateService = None,
        result_service: LLMAgentTaskRecoveryPreflightScheduleCleanupResultService = None,
        reporting_service: LLMAgentTaskRecoveryPreflightScheduleCleanupResultReportingService = None,
        retention_service: LLMAgentTaskRecoveryPreflightScheduleCleanupResultRetentionService = None,
    ):
        """
        Args:
            candidate_service: Defaults to a fresh service.
            result_service: Defaults to a fresh service; a defaulted
                reporting/retention service is built over it, so all
                three see the same persisted results.
        """
        self._candidate_service = (
            candidate_service
            if candidate_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleCleanupCandidateService()
        )
        self._result_service = (
            result_service if result_service is not None else LLMAgentTaskRecoveryPreflightScheduleCleanupResultService()
        )
        self._reporting_service = (
            reporting_service
            if reporting_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleCleanupResultReportingService(result_service=self._result_service)
        )
        self._retention_service = (
            retention_service
            if retention_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleCleanupResultRetentionService(result_service=self._result_service)
        )

    def summarize(
        self, task_id: str, now: Optional[datetime] = None, before: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleCleanupMaintenanceSummary:
        """
        Args:
            now: When candidates are evaluated; defaults to the current
                time.
            before: The retention cutoff, passed straight to the
                retention plan (its own default window when omitted).

        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupMaintenanceError: If
                task_id is not a non-empty string, or now/before is
                given and is not a datetime
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryScheduleCleanupMaintenanceError(
                "task_id is required and must be a non-empty string"
            )
        for value, name in ((now, "now"), (before, "before")):
            if value is not None and not isinstance(value, datetime):
                raise InvalidAgentTaskRecoveryScheduleCleanupMaintenanceError(f"{name} must be a datetime when given")
        now = now if now is not None else datetime.now(timezone.utc)

        candidates = self._candidate_service.find(task_id, now=now)
        latest = self._reporting_service.report(task_id) if self._result_service.history(task_id) else None
        retention_plan = self._retention_service.plan(task_id, before=before)

        return AgentTaskRecoveryScheduleCleanupMaintenanceSummary(
            task_id=task_id, summarized_at=now, current_candidates=candidates, outstanding_count=len(candidates),
            latest_result=latest,
            latest_cleaned_count=latest.cleaned_count if latest else None,
            latest_skipped_count=latest.skipped_count if latest else None,
            latest_failed_count=latest.failed_count if latest else None,
            last_maintenance_at=latest.executed_at if latest else None,
            historical_results=latest.historical_results if latest else (),
            retention_eligible=retention_plan.eligible, retention_protected=retention_plan.protected,
        )
