from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.agent_task_events.retention import DEFAULT_RETENTION_WINDOW

from .cleanup_batch import BATCH_FAILED
from .cleanup_result import LLMAgentTaskRecoveryPreflightScheduleCleanupResultService

PROTECTED_LATEST = "latest cleanup result for the task"
PROTECTED_UNRESOLVED_FAILURE = "records a failure that no later cleanup result has resolved"


class InvalidAgentTaskRecoveryScheduleCleanupResultRetentionError(ValueError):
    """Raised when plan()/apply() is given invalid arguments."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCleanupResultRetentionPlan:
    """plan()'s proposal: `eligible` result_ids that may be removed,
    `protected` (result_id, reason) pairs for results at or before
    `before` that must be kept. Results after `before` are not
    candidates at all."""

    task_id: str
    before: datetime
    eligible: tuple
    protected: tuple


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCleanupResultRetentionResult:
    """apply()'s outcome: `removed` result_ids actually removed,
    `already_removed` planned ones that were already gone, and
    `newly_protected` (result_id, reason) pairs that were planned but
    are protected at apply time and so kept."""

    task_id: str
    removed: tuple
    already_removed: tuple
    newly_protected: tuple


class LLMAgentTaskRecoveryPreflightScheduleCleanupResultRetentionService:
    """Bounds the #9 cleanup-result history -- never a new retention
    framework: the plan/apply split, the inclusive `before` cutoff, the
    removed/already_removed/newly_protected buckets, and the default
    window (backend.agent_task_events.retention.DEFAULT_RETENTION_WINDOW,
    30 days) all mirror backend.agent_task_events.
    LLMAgentTaskEventRetentionService, and the only removal is the #9
    result service's own remove().

    A result at or before the cutoff is eligible unless it is PROTECTED:
      - it is the task's latest result (the current one -- never removed);
      - it records a failed schedule that no later persisted result has
        recorded a non-failed outcome for (unresolved failure evidence).
    Protection is computed once from the full history, before any
    removal, so removing an old result can never turn an older one's
    resolved failure back into an unresolved one within the same pass.

    plan() is read-only. apply() re-classifies every planned result at
    apply time, so a stale or forged plan can never remove a protected
    result, and re-running it only reports already_removed. Removes only
    result records: schedules and their history are untouched and no
    cleanup or recovery runs.
    """

    def __init__(
        self,
        result_service: LLMAgentTaskRecoveryPreflightScheduleCleanupResultService = None,
        retention_window: timedelta = DEFAULT_RETENTION_WINDOW,
    ):
        self._result_service = (
            result_service if result_service is not None else LLMAgentTaskRecoveryPreflightScheduleCleanupResultService()
        )
        self._retention_window = retention_window

    def plan(
        self, task_id: str, before: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleCleanupResultRetentionPlan:
        """
        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupResultRetentionError:
                If task_id is not a non-empty string, or before is given
                and is not a datetime
        """
        self._require_text(task_id)
        if before is not None and not isinstance(before, datetime):
            raise InvalidAgentTaskRecoveryScheduleCleanupResultRetentionError("before must be a datetime when given")
        effective_before = before if before is not None else datetime.now(timezone.utc) - self._retention_window

        history = self._result_service.history(task_id)
        protection = self._protection(history)
        eligible, protected = [], []
        for record in history:
            if record.executed_at > effective_before:
                continue
            reason = protection.get(record.result_id)
            if reason is None:
                eligible.append(record.result_id)
            else:
                protected.append((record.result_id, reason))
        return AgentTaskRecoveryScheduleCleanupResultRetentionPlan(
            task_id=task_id, before=effective_before, eligible=tuple(eligible), protected=tuple(protected)
        )

    def apply(
        self, task_id: str, plan: AgentTaskRecoveryScheduleCleanupResultRetentionPlan = None
    ) -> AgentTaskRecoveryScheduleCleanupResultRetentionResult:
        """Remove every plan.eligible result still eligible right now
        (planning fresh when plan is None).

        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupResultRetentionError:
                If task_id is not a non-empty string, or plan is given
                and is not a retention plan for task_id
        """
        self._require_text(task_id)
        if plan is None:
            plan = self.plan(task_id)
        elif not isinstance(plan, AgentTaskRecoveryScheduleCleanupResultRetentionPlan):
            raise InvalidAgentTaskRecoveryScheduleCleanupResultRetentionError(
                "plan must be an AgentTaskRecoveryScheduleCleanupResultRetentionPlan"
            )
        elif plan.task_id != task_id:
            raise InvalidAgentTaskRecoveryScheduleCleanupResultRetentionError(
                f"plan belongs to task_id {plan.task_id!r}, not {task_id!r}"
            )

        history = self._result_service.history(task_id)
        present = {record.result_id for record in history}
        protection = self._protection(history)
        removed, already_removed, newly_protected = [], [], []
        for result_id in plan.eligible:
            if result_id not in present:
                already_removed.append(result_id)
            elif protection.get(result_id) is not None:
                newly_protected.append((result_id, protection[result_id]))
            elif self._result_service.remove(task_id, result_id):
                removed.append(result_id)
            else:
                already_removed.append(result_id)
        return AgentTaskRecoveryScheduleCleanupResultRetentionResult(
            task_id=task_id, removed=tuple(removed), already_removed=tuple(already_removed),
            newly_protected=tuple(newly_protected),
        )

    @staticmethod
    def _protection(history: tuple) -> dict:
        """result_id -> reason, for every result in history (oldest
        first) that must be kept."""
        protection = {}
        if history:
            protection[history[-1].result_id] = PROTECTED_LATEST
        for index, record in enumerate(history):
            if record.result_id in protection:
                continue
            for entry in record.entries:
                if entry.outcome != BATCH_FAILED:
                    continue
                resolved = any(
                    later.outcome != BATCH_FAILED
                    for later_record in history[index + 1:]
                    for later in later_record.entries
                    if later.schedule_id == entry.schedule_id
                )
                if not resolved:
                    protection[record.result_id] = PROTECTED_UNRESOLVED_FAILURE
                    break
        return protection

    @staticmethod
    def _require_text(task_id) -> None:
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryScheduleCleanupResultRetentionError(
                "task_id is required and must be a non-empty string"
            )
