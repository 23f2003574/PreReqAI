from datetime import datetime, timezone

from backend.agent_policy_engine import DENY
from backend.agent_task_event_analytics import (
    AgentTaskFailureRecoveryPlan,
    InvalidAgentTaskFailureRecoveryPlanError,
    LLMAgentTaskEventFailureRecoveryPlanner,
)

from .evaluation import LLMAgentTaskRecoveryGuardEvaluationService
from .models import AgentTaskRecoveryPreflightResult


class LLMAgentTaskRecoveryPreflightService:
    """Combines Commit #1(-of-agent_task_event_analytics)'s own recovery
    plan and Commit #2(-of-this-series)'s own guard evaluation into one
    single "what would happen right now" preflight snapshot -- never a
    third validation/policy layer (Rule: "Do not invent another
    validation/policy layer"): run()/run_plan() only ever call
    LLMAgentTaskEventFailureRecoveryPlanner.plan() and
    LLMAgentTaskRecoveryGuardEvaluationService.evaluate(), exactly once
    each, and bundle their two already-computed outputs -- nothing here
    re-plans, re-validates, or re-decides anything either of them already
    settled (Rule: "Reuse Commit #2 rather than duplicating guard
    evaluation").

    Read-only, never executes (Rule: "Never execute recovery"): neither
    collaborator this service calls ever mutates task state, and this
    service itself calls nothing from Commit #4(-of-agent_task_event_
    analytics)'s own execution service.

    Always evaluates CURRENT conditions, never a cached/stale plan (Rule:
    "Must evaluate current task conditions"): run() always calls plan()
    fresh, and Commit #2's own evaluate() already re-checks live state
    itself (via Commit #1's own guard) rather than trusting whatever the
    plan claims -- a plan that has gone stale between being built and
    being preflighted is exactly what that guard's own "plan_freshness"
    condition already catches, surfaced here unchanged.

    A genuine planning failure is reported, never hidden or fabricated
    into a plan (Rule: "If planning fails, report that failure instead of
    fabricating a plan"): if plan() raises anything OTHER than its own
    InvalidAgentTaskFailureRecoveryPlanError (a caller-input problem,
    always re-raised immediately rather than swallowed -- the same
    "validate your own inputs eagerly, contain a collaborator's failure
    gracefully" split this project's own multi-stage services already
    draw), run() catches it and returns a result with plan=None,
    guard_result=None, decision=DENY (Rule: "don't invent new status
    enums if existing ones fit" -- a recovery that cannot even be planned
    is exactly as unsafe to proceed with as one a real guard violation
    blocks), and blocking_reasons naming the failure itself.

    decision/blocking_reasons/warnings are always guard_result's own
    decision/blocking_rules/warnings verbatim whenever a guard_result
    exists -- this service never re-classifies Commit #2's own verdict.

    Deterministic apart from checked_at (Rule): every other field is a
    pure function of plan()/evaluate()'s own already-deterministic
    output; `now` is accepted explicitly (the same optional-`now`
    convention this project's other timestamped services already use)
    so a caller can pin it for exact, reproducible comparisons.
    """

    def __init__(
        self,
        planner: LLMAgentTaskEventFailureRecoveryPlanner = None,
        evaluation_service: LLMAgentTaskRecoveryGuardEvaluationService = None,
    ):
        self._planner = planner if planner is not None else LLMAgentTaskEventFailureRecoveryPlanner()
        self._evaluation_service = (
            evaluation_service if evaluation_service is not None else LLMAgentTaskRecoveryGuardEvaluationService()
        )

    def run(self, task_id: str, now: datetime = None) -> AgentTaskRecoveryPreflightResult:
        """Build task_id's current recovery plan fresh, then preflight it.

        Raises:
            InvalidAgentTaskFailureRecoveryPlanError: Propagated, not
                wrapped, from LLMAgentTaskEventFailureRecoveryPlanner.
                plan() if task_id is malformed
        """
        try:
            plan = self._planner.plan(task_id)
        except InvalidAgentTaskFailureRecoveryPlanError:
            raise
        except Exception as error:
            return AgentTaskRecoveryPreflightResult(
                task_id=task_id,
                plan=None,
                guard_result=None,
                decision=DENY,
                blocking_reasons=(f"recovery planning failed: {error}",),
                warnings=(),
                checked_at=now if now is not None else self._now(),
            )

        return self.run_plan(task_id, plan, now=now)

    def run_plan(
        self, task_id: str, recovery_plan: AgentTaskFailureRecoveryPlan, now: datetime = None
    ) -> AgentTaskRecoveryPreflightResult:
        """Preflight an already-computed recovery_plan exactly as given --
        never re-planned.

        Raises:
            InvalidAgentTaskRecoveryGuardError: Propagated, not wrapped,
                from LLMAgentTaskRecoveryGuardEvaluationService.evaluate()
                (via Commit #1's own guard) if task_id/recovery_plan is
                malformed
        """
        guard_result = self._evaluation_service.evaluate(task_id, recovery_plan)

        return AgentTaskRecoveryPreflightResult(
            task_id=task_id,
            plan=recovery_plan,
            guard_result=guard_result,
            decision=guard_result.decision,
            blocking_reasons=guard_result.blocking_rules,
            warnings=guard_result.warnings,
            checked_at=now if now is not None else self._now(),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
