from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend.agent_task_recovery_scheduling import LLMAgentTaskRecoveryPreflightSchedulingService

from .change_planner import (
    ACTION_ESCALATE,
    ACTION_EXPIRE,
    ACTION_NO_OP,
    ACTION_REVALIDATE,
    ACTION_WAIT,
    CHANGE_PLAN_ACTIONS,
    AgentTaskRecoveryScheduleDependencyChangePlan,
    LLMAgentTaskRecoveryPreflightScheduleDependencyChangePlanner,
)
from .timeout import TIMED_OUT

APPLIED = "applied"
REJECTED = "rejected"
FAILED = "failed"
APPLICATION_STATUSES = frozenset({APPLIED, REJECTED, FAILED})


class InvalidAgentTaskRecoveryScheduleDependencyChangeError(ValueError):
    """Raised when apply()/apply_schedule() is given invalid arguments
    -- a malformed change_plan, a task_id mismatch between task_id and
    change_plan.task_id, or an action not in CHANGE_PLAN_ACTIONS. Never
    raised for a stale/conflicting plan or a mid-batch execution failure
    -- both are reported as an ordinary result instead (Rule: "Reject
    stale/conflicting plans rather than blindly applying them" is a
    REPORTED outcome, not an exception)."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleChangeActionResult:
    """apply_schedule()'s own return value, and one entry in apply()'s
    own results tuple -- reported for EVERY item, whether applied,
    rejected, or failed (Rule: "Return per-schedule action, result, and
    reason").

    status is exactly one of APPLICATION_STATUSES:
        applied: the action was actually executed through its own
            existing service, successfully.
        rejected: NEVER executed at all -- the plan was stale (current
            re-classification no longer matches the requested action),
            conflicting (Commit #10's own conflict still stands), or
            evidence was insufficient. Rule: "Reject stale/conflicting
            plans rather than blindly applying them."
        failed: execution was attempted and the underlying existing
            service itself raised unexpectedly (Rule: covers "failure
            midway through a plan" -- apply() catches this per item and
            keeps processing the rest, never aborting the whole batch).

    new_schedule_id is the schedule_id now representing this same
    lineage after a successful wait/revalidate action (Commit #1-of-
    agent_task_recovery_scheduling's own cancel()+schedule() always
    mints a fresh one for those two) -- equal to schedule_id itself for
    escalate/expire/no_op/rejected/failed.

    preflight_id/dependency_id/dependency_state/dependency_evidence are
    Commit #10's own fresh plan item's own fields, carried through
    unchanged (Rule, added for Commit #12's own audit trail: "Preserve
    the exact dependency evidence used by the planner") -- the EXACT
    evidence this class itself based its own stale/conflict/action
    decision on, never re-derived afterward (state may have already
    moved on again by the time anything reads this result).
    previous_status/resulting_status are schedule_id's/new_schedule_id's
    own Commit #1-of-agent_task_recovery_scheduling status immediately
    before and after this call -- both None only when schedule_id itself
    could not be found at all.
    """

    task_id: str
    schedule_id: str
    action: Optional[str]
    status: str
    new_schedule_id: Optional[str]
    reason: str
    applied_at: datetime
    preflight_id: Optional[str] = None
    dependency_id: Optional[str] = None
    dependency_state: Optional[str] = None
    dependency_evidence: tuple = ()
    previous_status: Optional[str] = None
    resulting_status: Optional[str] = None


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleDependencyChangeResult:
    """apply()'s own complete report of one batch execution pass over
    every item in a Commit #10 change_plan."""

    task_id: str
    results: tuple
    applied_at: datetime


class LLMAgentTaskRecoveryPreflightScheduleDependencyChangeService:
    """Executes a Commit #10 change plan through the exact existing
    services that plan already named -- never a second execution engine
    (Rule: "Do not create another execution engine"): every state
    transition anywhere in this class is one already-idempotent, already-
    guardrail-respecting existing method call (Commit #4's own
    plan_wait()/apply_wait(), Commit #5's own wake_schedule(), Commit
    #7's own escalate(), Commit #6's own expire_wait(), or -- only when
    #6's own narrower TIMED_OUT precondition does not itself apply --
    Commit #1-of-agent_task_recovery_scheduling's own direct cancel())
    -- this class invents no new state transition of its own anywhere.

    Revalidates before every action that is not a plain no-op (Rule:
    "Revalidate before actions that require a current preflight" /
    "Validate the plan against current dependency/schedule state before
    applying it"): apply_schedule() always re-runs Commit #10's own
    planner FRESH for this exact schedule_id first, and compares that
    brand-new item against what was actually asked for -- never trusting
    a plan object's own recorded action, conflict, or evidence_sufficient
    fields as still current. A caller-supplied change_plan (from apply())
    is therefore only ever a WORK LIST of (schedule_id, action) pairs to
    attempt, never itself trusted as ground truth.

    Rejects rather than blindly applies (Rule: "Reject stale/conflicting
    plans..."): the fresh re-plan's own conflict (still standing) or
    evidence_sufficient=False refuses the action outright; a fresh
    action that no longer matches the one requested (the underlying
    dependency/schedule state has moved on since the plan was built) is
    reported REJECTED as stale -- never silently executed as if it were
    still correct, and never silently substituted with the new one
    either.

    Never dispatches or executes recovery (Rule): nothing in this class
    ever calls Commit #2-of-agent_task_recovery_scheduling's own
    dispatch(), or anything from backend.agent_task_recovery_guardrails'
    own consumption service or agent_task_event_analytics' own execution
    service.

    Idempotent by composition (Rule: "Make repeated application
    idempotent"): every underlying service this class calls is already
    idempotent on its own terms (Commit #4/#5/#6/#7's own docstrings),
    so a repeated apply_schedule() call for an action whose fresh
    re-plan still names it simply re-executes an already-idempotent
    call -- no special-case logic is added here. The one apparent
    exception is REVALIDATE: once wake_schedule() has already superseded
    schedule_id with a new one, schedule_id's own fresh re-plan now
    reads schedule_no_longer_viable (the old record is genuinely
    cancelled/superseded) rather than revalidation_required -- a second
    apply_schedule() call for the SAME (schedule_id, "revalidate") pair
    is then correctly reported REJECTED as stale, not silently re-run;
    the caller's own next real action belongs to the NEW schedule_id.
    WAIT needs one small piece of genuinely new logic here (the ONLY
    execution-time idempotency check in this class, everything else is
    inherited from the underlying service): a schedule_id already
    deferred and still within that own wait window is reported APPLIED
    as a plain no-op WITHOUT calling Commit #4's own plan_wait() again
    -- that method's own validate() call requires the schedule be
    currently due, which a still-waiting schedule, by definition, is
    not; without this check a legitimate repeat call would surface as a
    FAILED execution rather than the idempotent no-op it actually is.

    apply(task_id, change_plan) never aborts on one item's own failure
    (Rule: "failure midway through a plan"): each item is applied
    independently, an unexpected exception from the underlying service
    is caught and reported as that one item's own status=FAILED result,
    and every other item is still attempted.
    """

    def __init__(
        self,
        planner_service: LLMAgentTaskRecoveryPreflightScheduleDependencyChangePlanner = None,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        wait_service=None,
        wake_service=None,
        escalation_service=None,
        timeout_service=None,
        audit_service=None,
    ):
        """
        Args:
            planner_service: Commit #10's own planner -- the sole
                source of "what does this schedule need right now."
                Defaults to a fresh
                LLMAgentTaskRecoveryPreflightScheduleDependencyChangePlanner
                built over scheduling_service (no impact_service of its
                own wired to real dependency data -- every schedule
                would plan as no_impact; pass the real, wired instance
                for this service to ever execute anything).
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService; used for
                the direct cancel() fallback an "expire" action takes
                when Commit #6's own narrower TIMED_OUT precondition
                does not apply.
            wait_service: No default. Required for a successful "wait"
                action; its absence when one is attempted is reported as
                that item's own status=FAILED result, never a crash.
            wake_service: No default. Required for "revalidate".
            escalation_service: No default. Required for "escalate".
            timeout_service: No default. Optional even for "expire" --
                when omitted, every expire falls straight through to the
                direct cancel() fallback.
            audit_service: No default. When given, Commit #12's own
                LLMAgentTaskRecoveryPreflightScheduleDependencyChangeAuditService.
                record() is called automatically for every
                apply_schedule() result (applied, rejected, or failed
                alike), whether called directly or from inside apply()'s
                own batch loop; omitted, no audit trail is recorded.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._planner_service = (
            planner_service
            if planner_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDependencyChangePlanner(
                scheduling_service=self._scheduling_service
            )
        )
        self._wait_service = wait_service
        self._wake_service = wake_service
        self._escalation_service = escalation_service
        self._timeout_service = timeout_service
        self._audit_service = audit_service

    def apply(
        self, task_id: str, change_plan: AgentTaskRecoveryScheduleDependencyChangePlan, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleDependencyChangeResult:
        """Apply every item in change_plan, independently. Never raises
        for a stale/conflicting/failed item -- see this class's own
        docstring.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyChangeError: If
                task_id is not a non-empty string, now is given and is
                not a datetime, change_plan is not an
                AgentTaskRecoveryScheduleDependencyChangePlan, or
                change_plan.task_id does not match task_id
        """
        self._require_text(task_id, "task_id")
        now = self._resolve_now(now)
        if not isinstance(change_plan, AgentTaskRecoveryScheduleDependencyChangePlan):
            raise InvalidAgentTaskRecoveryScheduleDependencyChangeError(
                "change_plan must be an AgentTaskRecoveryScheduleDependencyChangePlan"
            )
        if change_plan.task_id != task_id:
            raise InvalidAgentTaskRecoveryScheduleDependencyChangeError(
                "change_plan does not name this exact task_id"
            )

        results = []
        for item in change_plan.items:
            current_schedule = self._scheduling_service.get(task_id, item.schedule_id)
            current_status = current_schedule.status if current_schedule is not None else None
            if item.action is None:
                reason = item.conflict.reason if item.conflict is not None else item.reason
                rejected = self._result(
                    task_id, item.schedule_id, None, REJECTED, item.schedule_id, reason, now,
                    item=item, previous_status=current_status, resulting_status=current_status,
                )
                self._maybe_audit(task_id, item.schedule_id, rejected)
                results.append(rejected)
                continue
            try:
                # apply_schedule() itself already audits its own result
                # (Rule: "Integrate with the #11 change-execution
                # service") -- never audited a second time here.
                results.append(self.apply_schedule(task_id, item.schedule_id, item.action, now=now))
            except InvalidAgentTaskRecoveryScheduleDependencyChangeError:
                raise
            except Exception as error:
                failed = self._result(
                    task_id, item.schedule_id, item.action, FAILED, item.schedule_id,
                    f"execution failed: {error}", now,
                    item=item, previous_status=current_status, resulting_status=current_status,
                )
                self._maybe_audit(task_id, item.schedule_id, failed)
                results.append(failed)

        return AgentTaskRecoveryScheduleDependencyChangeResult(task_id=task_id, results=tuple(results), applied_at=now)

    def apply_schedule(
        self, task_id: str, schedule_id: str, action: str, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleChangeActionResult:
        """Apply exactly one action to task_id's exact schedule_id,
        after re-validating it against current state.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyChangeError: If
                task_id/schedule_id is not a non-empty string, now is
                given and is not a datetime, action is not one of
                CHANGE_PLAN_ACTIONS, or schedule_id names no recorded
                schedule for task_id (propagated from Commit #10's own
                plan())
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        if action not in CHANGE_PLAN_ACTIONS:
            raise InvalidAgentTaskRecoveryScheduleDependencyChangeError(
                f"action must be one of {sorted(CHANGE_PLAN_ACTIONS)}, got {action!r}"
            )
        now = self._resolve_now(now)

        fresh_plan = self._planner_service.plan(task_id, schedule_id=schedule_id, now=now)
        fresh_item = fresh_plan.items[0]
        current_schedule = self._scheduling_service.get(task_id, schedule_id)
        previous_status = current_schedule.status if current_schedule is not None else None

        if fresh_item.conflict is not None:
            result = self._result(
                task_id, schedule_id, action, REJECTED, schedule_id,
                f"plan is conflicting: {fresh_item.conflict.reason}", now,
                item=fresh_item, previous_status=previous_status, resulting_status=previous_status,
            )
        elif not fresh_item.evidence_sufficient:
            result = self._result(
                task_id, schedule_id, action, REJECTED, schedule_id, f"cannot apply: {fresh_item.reason}", now,
                item=fresh_item, previous_status=previous_status, resulting_status=previous_status,
            )
        elif fresh_item.action != action:
            result = self._result(
                task_id, schedule_id, action, REJECTED, schedule_id,
                f"plan is stale: current required action is {fresh_item.action!r}, not {action!r}", now,
                item=fresh_item, previous_status=previous_status, resulting_status=previous_status,
            )
        else:
            new_schedule_id, reason = self._execute(task_id, schedule_id, action, fresh_item, now)
            resulting_schedule = self._scheduling_service.get(task_id, new_schedule_id)
            resulting_status = resulting_schedule.status if resulting_schedule is not None else None
            result = self._result(
                task_id, schedule_id, action, APPLIED, new_schedule_id, reason, now,
                item=fresh_item, previous_status=previous_status, resulting_status=resulting_status,
            )

        self._maybe_audit(task_id, schedule_id, result)
        return result

    def _maybe_audit(self, task_id: str, schedule_id: str, result: AgentTaskRecoveryScheduleChangeActionResult) -> None:
        if self._audit_service is not None:
            self._audit_service.record(task_id, schedule_id, result)

    def _execute(self, task_id: str, schedule_id: str, action: str, item, now: datetime) -> tuple:
        if action == ACTION_NO_OP:
            return schedule_id, "no action needed"

        if action == ACTION_REVALIDATE:
            if self._wake_service is None:
                raise InvalidAgentTaskRecoveryScheduleDependencyChangeError("no wake_service configured for revalidate")
            outcome = self._wake_service.wake_schedule(task_id, schedule_id, now=now)
            return outcome.schedule_id, outcome.reason

        if action == ACTION_WAIT:
            if self._wait_service is None:
                raise InvalidAgentTaskRecoveryScheduleDependencyChangeError("no wait_service configured for wait")
            # Idempotent no-op (Rule) when this exact schedule_id is
            # already deferred and still within that own wait window --
            # Commit #4's own plan_wait() would otherwise refuse it
            # outright (its own validate() call requires the schedule be
            # currently due), which is correct for #4's own direct
            # callers but would wrongly surface as a FAILED execution
            # here for a schedule this exact action already handled.
            current = self._scheduling_service.get(task_id, schedule_id)
            if current is not None and current.execute_at is not None and current.execute_at > now:
                return schedule_id, f"already deferred until {current.execute_at.isoformat()}"
            wait_plan = self._wait_service.plan_wait(task_id, schedule_id, now=now)
            applied = self._wait_service.apply_wait(task_id, schedule_id, wait_plan, now=now)
            return applied.schedule_id, f"deferred to {wait_plan.next_check_at.isoformat()}"

        if action == ACTION_ESCALATE:
            if self._escalation_service is None:
                raise InvalidAgentTaskRecoveryScheduleDependencyChangeError(
                    "no escalation_service configured for escalate"
                )
            result = self._escalation_service.escalate(task_id, schedule_id, now=now)
            return schedule_id, result.reason

        if action == ACTION_EXPIRE:
            return self._execute_expire(task_id, schedule_id, item, now)

        raise InvalidAgentTaskRecoveryScheduleDependencyChangeError(f"unsupported action {action!r}")

    def _execute_expire(self, task_id: str, schedule_id: str, item, now: datetime) -> tuple:
        if self._timeout_service is not None:
            timeout_result = self._timeout_service.check(task_id, schedule_id, now=now)
            if timeout_result.state == TIMED_OUT:
                cancelled = self._timeout_service.expire_wait(task_id, schedule_id, now=now)
                return cancelled.schedule_id, cancelled.cancellation_reason or "dependency wait timed out"

        cancelled = self._scheduling_service.cancel(
            task_id, schedule_id, reason=f"dependency no longer viable: {item.reason}"
        )
        return cancelled.schedule_id, cancelled.cancellation_reason

    @staticmethod
    def _result(
        task_id, schedule_id, action, status, new_schedule_id, reason, now,
        item=None, previous_status=None, resulting_status=None,
    ):
        return AgentTaskRecoveryScheduleChangeActionResult(
            task_id=task_id, schedule_id=schedule_id, action=action, status=status,
            new_schedule_id=new_schedule_id, reason=reason, applied_at=now,
            preflight_id=item.preflight_id if item is not None else None,
            dependency_id=item.dependency_id if item is not None else None,
            dependency_state=item.dependency_state if item is not None else None,
            dependency_evidence=item.dependency_evidence if item is not None else (),
            previous_status=previous_status, resulting_status=resulting_status,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleDependencyChangeError(
                f"{field_name} is required and must be a non-empty string"
            )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleDependencyChangeError("now must be a datetime when given")
        return now
