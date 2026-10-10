from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend.agent_task_recovery_guardrails import (
    LLMAgentTaskRecoveryGuardEvaluationService,
    LLMAgentTaskRecoveryPreflightStore,
)

from .models import SCHEDULED
from .service import LLMAgentTaskRecoveryPreflightSchedulingService
from .validation import LLMAgentTaskRecoveryPreflightScheduleValidationService

_MAX_DATETIME = datetime.max.replace(tzinfo=timezone.utc)


class InvalidAgentTaskRecoverySchedulePriorityError(ValueError):
    """Raised when prioritize()/priority() is given invalid arguments."""


@dataclass(frozen=True)
class AgentTaskRecoverySchedulePriority:
    """One schedule's own explainable priority factors -- never itself a
    decision to dispatch/authorize/execute anything (Rule: "Keep this
    service read-only; dispatch/execution remains elsewhere").

    actionable is exactly Commit #2's own is_executable() (Rule: "Invalid/
    cancelled/stale schedules must not become actionable merely through
    priority" -- computing a rank for one never overrides that verdict).
    recovery_priority/risk_level are None when the schedule is not
    actionable at all, or no evaluation_service was supplied -- never
    guessed.
    """

    task_id: str
    schedule_id: str
    preflight_id: str
    actionable: bool
    recovery_priority: Optional[int]
    execute_at: Optional[datetime]
    risk_level: Optional[str]
    factors: tuple


class LLMAgentTaskRecoveryPreflightSchedulePriorityService:
    """Orders a task's own actionable Commit #1 schedules deterministically
    -- never a second queue or priority system (Rule: "Do not create a
    second queue or priority system"): every signal considered is read
    straight from an existing source, none re-derived:

        recovery urgency / policy   backend.agent_task_event_analytics'
                                     own Commit #3 AgentTaskFailureRecoveryPlan.
                                     priority (RECOVERY_PRIORITY_HIGH/
                                     MEDIUM/LOW/NONE) -- this repository's
                                     own already-established "higher
                                     first" recovery-urgency scale
        retry/deadline information   the schedule's own execute_at
                                     (earlier deadline ranks first)
        task risk                   a fresh Commit #2-of-agent_task_
                                     recovery_guardrails evaluate() call's
                                     own risk_level, only when an
                                     evaluation_service is supplied
        eligibility/readiness       Commit #2-of-this-series' own
                                     is_executable() -- a schedule that
                                     is not currently actionable is
                                     excluded from ranking altogether,
                                     never merely ranked last

    Sort key, fully deterministic (Rule: "Deterministic ordering for
    identical state"; explicit tie-break, Rule: "equal-priority ties"):
    (-recovery_priority, execute_at or +inf, schedule_id) -- higher
    recovery_priority first, then earlier execute_at, then schedule_id as
    the final, always-unique tiebreaker.

    Read-only (Rule): prioritize()/priority() never call schedule()/
    cancel()/dispatch()/authorize()/consume() -- only Commit #1's own
    list()/get(), Commit #2's own is_executable(), Commit #4(-of-agent_
    task_recovery_guardrails)'s own preflight history, and (optionally)
    Commit #2(-of-agent_task_recovery_guardrails)'s own evaluate().
    """

    def __init__(
        self,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        validation_service: LLMAgentTaskRecoveryPreflightScheduleValidationService = None,
        preflight_store: LLMAgentTaskRecoveryPreflightStore = None,
        evaluation_service: LLMAgentTaskRecoveryGuardEvaluationService = None,
    ):
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._validation_service = (
            validation_service
            if validation_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleValidationService(scheduling_service=self._scheduling_service)
        )
        self._preflight_store = (
            preflight_store if preflight_store is not None else LLMAgentTaskRecoveryPreflightStore()
        )
        self._evaluation_service = evaluation_service

    def prioritize(self, task_id: str, schedules: list = None) -> tuple:
        """The actionable subset of schedules, ordered deterministically,
        most urgent first. Defaults to task_id's own schedules (Commit
        #1's own list()) when schedules is omitted; when schedules is
        given explicitly, it may span multiple tasks (a caller's own
        already-gathered candidate set) -- each schedule is evaluated
        against its OWN task_id, never the outer task_id parameter, so a
        multi-task candidate list is ordered correctly.

        Raises:
            InvalidAgentTaskRecoverySchedulePriorityError: If task_id is
                not a non-empty string
        """
        self._require_text(task_id, "task_id")
        candidates = schedules if schedules is not None else self._scheduling_service.list(task_id)

        priorities = [self._priority_for(schedule.task_id, schedule) for schedule in candidates]
        actionable = [p for p in priorities if p.actionable]
        actionable.sort(key=self._sort_key)
        return tuple(actionable)

    def priority(self, task_id: str, schedule_id: str) -> AgentTaskRecoverySchedulePriority:
        """task_id's exact schedule_id's own priority factors, whether or
        not it is currently actionable.

        Raises:
            InvalidAgentTaskRecoverySchedulePriorityError: If task_id or
                schedule_id is not a non-empty string, or schedule_id
                names no recorded schedule for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        schedule = self._scheduling_service.get(task_id, schedule_id)
        if schedule is None:
            raise InvalidAgentTaskRecoverySchedulePriorityError(
                f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
            )
        return self._priority_for(task_id, schedule)

    def _priority_for(self, task_id: str, schedule) -> AgentTaskRecoverySchedulePriority:
        actionable = self._validation_service.is_executable(task_id, schedule.schedule_id)

        recovery_priority = None
        factors = [f"actionable={actionable}"]
        risk_level = None

        if actionable:
            preflight = next(
                (r for r in self._preflight_store.history(task_id) if r.preflight_id == schedule.preflight_id), None
            )
            if preflight is not None and preflight.plan is not None:
                recovery_priority = preflight.plan.priority
                factors.append(f"recovery_priority={recovery_priority}")
                if self._evaluation_service is not None:
                    evaluation = self._evaluation_service.evaluate(task_id, preflight.plan)
                    risk_level = evaluation.risk_level
                    factors.append(f"risk_level={risk_level}")
            if schedule.execute_at is not None:
                factors.append(f"execute_at={schedule.execute_at.isoformat()}")

        return AgentTaskRecoverySchedulePriority(
            task_id=task_id, schedule_id=schedule.schedule_id, preflight_id=schedule.preflight_id,
            actionable=actionable, recovery_priority=recovery_priority, execute_at=schedule.execute_at,
            risk_level=risk_level, factors=tuple(factors),
        )

    @staticmethod
    def _sort_key(priority: AgentTaskRecoverySchedulePriority):
        # scheduling_service.list() only ever returns records that already
        # carry created_at; re-fetch it here via the same field for the
        # deterministic tiebreak.
        return (
            -(priority.recovery_priority or 0),
            priority.execute_at or _MAX_DATETIME,
            priority.schedule_id,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoverySchedulePriorityError(
                f"{field_name} is required and must be a non-empty string"
            )
