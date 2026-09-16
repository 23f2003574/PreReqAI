from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from backend.agent_task_recovery_scheduling import LLMAgentTaskRecoveryPreflightSchedulingService

from .impact import (
    ESCALATION_REQUIRED,
    NO_IMPACT,
    REVALIDATION_REQUIRED,
    SCHEDULE_NO_LONGER_VIABLE,
    WAITING_REQUIRED,
    LLMAgentTaskRecoveryPreflightScheduleDependencyImpactService,
)

ACTION_REVALIDATE = "revalidate"
ACTION_WAIT = "wait"
ACTION_ESCALATE = "escalate"
ACTION_EXPIRE = "expire"
ACTION_NO_OP = "no_op"
CHANGE_PLAN_ACTIONS = frozenset({ACTION_REVALIDATE, ACTION_WAIT, ACTION_ESCALATE, ACTION_EXPIRE, ACTION_NO_OP})

# The one, fixed mapping from Commit #9's own impact category to the
# single existing repository action that addresses it -- never a second
# decision formula (Rule: "Never invent an action unsupported by the
# repository"): every value on the right is a REAL, already-existing
# method on an already-existing service in this package or backend.
# agent_task_recovery_scheduling; this module never calls any of them.
_CATEGORY_TO_ACTION = {
    NO_IMPACT: ACTION_NO_OP,
    REVALIDATION_REQUIRED: ACTION_REVALIDATE,
    WAITING_REQUIRED: ACTION_WAIT,
    ESCALATION_REQUIRED: ACTION_ESCALATE,
    SCHEDULE_NO_LONGER_VIABLE: ACTION_EXPIRE,
}

_ACTION_TO_SERVICE = {
    ACTION_REVALIDATE: "LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService.wake_schedule",
    ACTION_WAIT: "LLMAgentTaskRecoveryPreflightScheduleDependencyWaitService.plan_wait/apply_wait",
    ACTION_ESCALATE: "LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService.escalate",
    ACTION_EXPIRE: "LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService.expire_wait",
    ACTION_NO_OP: None,
}

# Deterministic ordering (Rule: "ordering ... between actions" / "Make
# identical inputs produce deterministic plans") -- most urgent/
# terminal first, since an expire/escalate decision is never made moot
# by a later, less urgent one, while the reverse is not true. A plan
# item with no action at all (insufficient evidence, or a detected
# conflict) sorts last -- there is nothing yet to act on.
_ACTION_PRIORITY = {
    ACTION_EXPIRE: 0,
    ACTION_ESCALATE: 1,
    ACTION_WAIT: 2,
    ACTION_REVALIDATE: 3,
    ACTION_NO_OP: 4,
    None: 5,
}


class InvalidAgentTaskRecoveryScheduleDependencyChangePlanError(ValueError):
    """Raised when plan() is given invalid arguments, or schedule_id
    (when given) names no recorded schedule for task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleChangePlanConflict:
    """Recorded whenever two existing repository signals disagree about
    what a schedule needs next (Rule: "Detect conflicting actions rather
    than silently choosing one") -- the ONE conflict this planner
    currently detects: Commit #7's own escalation history shows this
    exact schedule already escalated and (per an optional Commit #8
    escalation_resolution_service) not yet resolved, while Commit #9's
    own fresh impact analysis now suggests a DIFFERENT action. Both
    candidates are preserved, never silently collapsed into one."""

    schedule_id: str
    candidate_actions: tuple
    reason: str


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleChangePlanItem:
    """One schedule's own concrete, reviewable plan entry -- never a
    bare action label (Rule: "Preserve enough evidence for review/
    audit"): dependency_state/dependency_evidence/changes are Commit
    #9's own AgentTaskRecoveryScheduleDependencyImpactOutcome fields,
    carried through unchanged, never recomputed.

    action is exactly one of CHANGE_PLAN_ACTIONS, or None in two cases,
    both deliberately never guessed past (Rule: "Never invent an
    action..." / "Detect conflicting actions rather than silently
    choosing one"): evidence_sufficient is False (Commit #9's own
    incomplete-evidence signal, reused verbatim), or conflict is not
    None. affected_service names the exact existing method that WOULD
    perform this action -- this planner itself never calls it (Rule:
    "Planning only; no state mutation and no recovery execution").

    sequence is this item's own 0-based position in the plan's own
    deterministic ordering (Rule: "ordering/dependencies between
    actions") -- ties broken by schedule_id, so identical inputs always
    produce the identical ordering.
    """

    task_id: str
    schedule_id: str
    preflight_id: Optional[str]
    dependency_id: Optional[str]
    dependency_state: Optional[str]
    action: Optional[str]
    affected_service: Optional[str]
    reason: str
    evidence_sufficient: bool
    dependency_evidence: tuple
    changes: tuple
    conflict: Optional[AgentTaskRecoveryScheduleChangePlanConflict]
    sequence: int


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleDependencyChangePlan:
    """plan()'s own complete, deterministic, auditable report -- every
    affected schedule for task_id (or the exact one named by
    schedule_id), each with its own AgentTaskRecoveryScheduleChangePlanItem,
    in this plan's own fixed ordering."""

    task_id: str
    schedule_id: Optional[str]
    dependency_id: Optional[str]
    items: tuple
    planned_at: datetime
    plan_id: str = field(default_factory=lambda: str(uuid4()))


class LLMAgentTaskRecoveryPreflightScheduleDependencyChangePlanner:
    """Turns Commit #9's own dependency-impact analysis into a concrete,
    reviewable action plan -- never a second decision engine (Rule: "Do
    not create another decision engine"): every fact here is Commit #9's
    own AgentTaskRecoveryScheduleDependencyImpactOutcome, read straight
    through unchanged; this class adds exactly one thing Commit #9 does
    not already provide -- naming which single EXISTING service/method
    would act on that classification, and in what order -- and nothing
    else.

    plan() never calls anything that could mutate a schedule, a task, a
    dependency edge, a block/wait/escalation record, or execute recovery
    (Rule: "Planning only; no state mutation and no recovery
    execution") -- not because it holds no reference to those services
    at all (it takes optional escalation_service/escalation_resolution_
    service collaborators, purely to READ their own already-persisted
    history for conflict detection), but because it never calls a single
    write method on any of them, anywhere in this class.

    Action mapping is fixed and total (Rule: "Base decisions on existing
    dependency-impact and scheduling rules" / "Never invent an action
    unsupported by the repository") -- see _CATEGORY_TO_ACTION's own
    module-level docstring for the exact, five-entry table; there is no
    other path to an action value anywhere in this class.

    Conflict detection (Rule: "Detect conflicting actions rather than
    silently choosing one") is the one piece of genuinely new logic
    here, and it is deliberately narrow: a schedule Commit #7 already
    escalated, and (per escalation_resolution_service, when supplied)
    not yet resolved, whose Commit #9 impact category is anything other
    than escalation_required, gets action=None and a recorded
    AgentTaskRecoveryScheduleChangePlanConflict naming both candidates
    -- this planner never silently picks the impact-based action over
    the standing escalation, or vice versa.

    Deterministic (Rule: "Make identical inputs produce deterministic
    plans"): every read here is itself already deterministic for fixed
    `now` (Commit #9's own analyze()/analyze_schedule() guarantee this),
    and item ordering is a pure, fixed function of (action priority,
    schedule_id) -- never insertion order or any other incidental
    detail.
    """

    def __init__(
        self,
        impact_service: LLMAgentTaskRecoveryPreflightScheduleDependencyImpactService = None,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        escalation_service=None,
        escalation_resolution_service=None,
    ):
        """
        Args:
            impact_service: Commit #9's own impact service -- the sole
                source of every classification this planner turns into
                an action. Defaults to a fresh
                LLMAgentTaskRecoveryPreflightScheduleDependencyImpactService
                built over scheduling_service (no reconciliation_service
                of its own -- every schedule would classify as
                no_impact; pass the real, wired instance for this
                planner to ever produce a meaningful plan).
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService; used
                only to validate an explicitly given schedule_id exists
                before ever consulting impact_service.
            escalation_service: No default. When given, its own
                get_history() is read (never written) to detect the one
                conflict class this planner recognizes.
            escalation_resolution_service: No default. When given
                alongside escalation_service, its own get_history() is
                also read (never written) to tell an ALREADY-resolved
                escalation apart from one still standing.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._impact_service = (
            impact_service
            if impact_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDependencyImpactService(
                scheduling_service=self._scheduling_service
            )
        )
        self._escalation_service = escalation_service
        self._escalation_resolution_service = escalation_resolution_service

    def plan(
        self,
        task_id: str,
        schedule_id: str = None,
        dependency_id: str = None,
        now: Optional[datetime] = None,
    ) -> AgentTaskRecoveryScheduleDependencyChangePlan:
        """Build a deterministic, reviewable change plan for task_id --
        every schedule recorded for it, narrowed to schedule_id or
        dependency_id when given (schedule_id takes priority over
        dependency_id when both are given).

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyChangePlanError:
                If task_id is not a non-empty string, schedule_id/
                dependency_id is given and is not a non-empty string,
                now is given and is not a datetime, or schedule_id is
                given and names no recorded schedule for task_id
        """
        self._require_text(task_id, "task_id")
        if schedule_id is not None:
            self._require_text(schedule_id, "schedule_id")
        if dependency_id is not None:
            self._require_text(dependency_id, "dependency_id")
        now = self._resolve_now(now)

        if schedule_id is not None:
            if self._scheduling_service.get(task_id, schedule_id) is None:
                raise InvalidAgentTaskRecoveryScheduleDependencyChangePlanError(
                    f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
                )
            outcomes = [self._impact_service.analyze_schedule(task_id, schedule_id, now=now)]
        else:
            outcomes = list(self._impact_service.analyze(task_id, dependency_id=dependency_id, now=now).outcomes)

        items = [self._plan_item(task_id, outcome, now) for outcome in outcomes]
        ordered = sorted(items, key=lambda item: (_ACTION_PRIORITY[item.action], item.schedule_id))
        ordered = tuple(replace(item, sequence=index) for index, item in enumerate(ordered))

        return AgentTaskRecoveryScheduleDependencyChangePlan(
            task_id=task_id, schedule_id=schedule_id, dependency_id=dependency_id, items=ordered, planned_at=now,
        )

    def _plan_item(self, task_id: str, outcome, now: datetime) -> AgentTaskRecoveryScheduleChangePlanItem:
        if not outcome.evidence_sufficient:
            return self._item(task_id, outcome, None, None, outcome.reason, None)

        conflict = self._detect_conflict(task_id, outcome.schedule_id, outcome.category)
        if conflict is not None:
            return self._item(task_id, outcome, None, None, conflict.reason, conflict)

        action = _CATEGORY_TO_ACTION[outcome.category]
        affected_service = _ACTION_TO_SERVICE[action]
        return self._item(task_id, outcome, action, affected_service, outcome.reason, None)

    def _detect_conflict(
        self, task_id: str, schedule_id: str, impact_category: Optional[str]
    ) -> Optional[AgentTaskRecoveryScheduleChangePlanConflict]:
        if self._escalation_service is None:
            return None
        escalation_history = self._escalation_service.get_history(task_id, schedule_id)
        if not escalation_history:
            return None
        if self._escalation_resolution_service is not None:
            resolution_history = self._escalation_resolution_service.get_history(task_id, schedule_id)
            if resolution_history:
                return None
        if impact_category == ESCALATION_REQUIRED:
            return None

        impact_action = _CATEGORY_TO_ACTION.get(impact_category)
        return AgentTaskRecoveryScheduleChangePlanConflict(
            schedule_id=schedule_id,
            candidate_actions=(ACTION_ESCALATE, impact_action),
            reason=(
                f"schedule {schedule_id!r} is already escalated and not yet resolved, but current dependency "
                f"analysis suggests {impact_action!r} instead"
            ),
        )

    @staticmethod
    def _item(task_id, outcome, action, affected_service, reason, conflict) -> AgentTaskRecoveryScheduleChangePlanItem:
        return AgentTaskRecoveryScheduleChangePlanItem(
            task_id=task_id, schedule_id=outcome.schedule_id, preflight_id=outcome.preflight_id,
            dependency_id=outcome.dependency_id, dependency_state=outcome.dependency_state, action=action,
            affected_service=affected_service, reason=reason, evidence_sufficient=outcome.evidence_sufficient,
            dependency_evidence=outcome.dependency_evidence, changes=outcome.changes, conflict=conflict, sequence=0,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleDependencyChangePlanError(
                f"{field_name} is required and must be a non-empty string"
            )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleDependencyChangePlanError("now must be a datetime when given")
        return now
