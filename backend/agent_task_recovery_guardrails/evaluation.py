from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_policy_risk_assessment import LEVELS
from backend.agent_policy_risk_thresholds import REVIEW
from backend.agent_task_event_analytics import RECOVERY_ACTION_RETRY, AgentTaskFailureRecoveryPlan

from .guard import LLMAgentTaskRecoveryGuardService
from .models import AgentTaskRecoveryGuardEvaluation

# Conditions Commit #1's own guard always attempts whenever their own
# collaborator was supplied, regardless of the plan's own recommended
# action -- "retry_budget" is deliberately excluded here since it only
# ever applies to RECOVERY_ACTION_RETRY (see _applicable_conditions()).
_UNCONDITIONALLY_APPLICABLE_CONDITIONS = (
    "action_permission",
    "dependency_readiness",
    "conflicting_recovery",
    "active_reservation",
    "dead_letter_status",
)


def _applicable_conditions(action: str) -> frozenset:
    conditions = set(_UNCONDITIONALLY_APPLICABLE_CONDITIONS)
    if action == RECOVERY_ACTION_RETRY:
        conditions.add("retry_budget")
    return frozenset(conditions)


class InvalidAgentTaskRecoveryGuardEvaluationError(ValueError):
    """Raised when evaluate() is given invalid arguments, or an optional
    risk_level_resolver returns a value outside this repository's own
    risk vocabulary."""


class LLMAgentTaskRecoveryGuardEvaluationService:
    """Turns Commit #1's own AgentTaskRecoveryGuardResult into one
    coarser, structured decision -- allow / deny / review -- never a
    second validation framework (Rule: "Do not create another validation
    framework"; "Guardrails remain the source of truth for constraint
    checks"): evaluate() calls LLMAgentTaskRecoveryGuardService.validate()
    exactly once and every fact on the returned AgentTaskRecoveryGuardEvaluation
    is derived from that one call's own already-computed
    violations/warnings/checked_conditions -- nothing here re-runs, re-
    checks, or second-guesses any individual constraint Commit #1 already
    evaluated.

    Read-only, never executes (Rule): evaluate() never calls anything
    from backend.agent_task_event_analytics' own Commit #4 execution
    service, and the guard_service it composes is itself already fully
    read-only.

    decision reuses this repository's own existing tri-state vocabulary
    verbatim (Rule: "Reuse existing risk/policy semantics; don't invent
    categories") -- backend.agent_policy_engine.ALLOW/DENY (the base
    binary values every policy-adjacent module in this repository already
    shares) plus backend.agent_policy_risk_thresholds.REVIEW (the one
    place a genuine three-way ALLOW/REVIEW/DENY vocabulary already exists
    in this repository, for backend.agent_policy_risk_decision's own
    scope_id-scoped domain). Only the three string VALUES are reused here
    -- not RiskThresholds/LLMAgentPolicyRiskDecisionEngine themselves,
    both of which are scoped to a policy scope_id/action_context, an
    identity space this task_id-scoped recovery-guard domain does not
    share (the same non-reuse finding this project's own memory already
    documents repeatedly for other cross-domain modules) -- reusing their
    class/engine directly here would require fabricating a scope_id that
    does not exist for a recovery decision, which is exactly the kind of
    invented mapping "don't invent categories" warns against.

    DENY whenever Commit #1 found ANY violation -- a real, evidence-backed
    hard constraint always wins over everything else, regardless of what
    else this call also found. REVIEW whenever nothing is outright
    blocking, but either Commit #1 itself reported a warning (e.g. a
    RECOVERY_ACTION_WAIT_FOR_DEPENDENCY plan whose dependencies are still
    unresolved), or a condition applicable to this plan's own
    recommended_action was never actually verified at all -- because the
    guard's own optional collaborator for it (readiness_service/
    retry_eligibility_service/retry_scheduler/dead_letter_service/
    reservation_service) was never supplied (Rule: "Never silently convert
    an unknown condition into 'allow'": an unverified condition is treated
    as "needs a human to look," never as license to proceed as if it had
    passed). ALLOW only when every condition applicable to this specific
    action was positively checked, with nothing to report at all.

    risk_level is populated ONLY through an optional `risk_level_resolver`
    collaborator (Rule: "risk_level only if an existing risk model
    supports it") -- a plain callable `(task_id, recovery_plan,
    guard_result) -> Optional[str]` a caller supplies when they separately
    have a way to map this recovery decision onto a real, existing risk
    model (e.g. their own scope_id-scoped backend.agent_policy_risk_assessment
    pipeline) -- this service has no such mapping of its own, and invents
    none. Whatever the resolver returns must be one of backend.
    agent_policy_risk_assessment.LEVELS (LOW/MEDIUM/HIGH/CRITICAL) or None
    -- enforced here, never trusted blindly, so a misconfigured resolver
    cannot smuggle a new, invented risk category onto this result.

    Deterministic (Rule): guard_service.validate() is itself already
    deterministic, and every step here is a pure function of its own
    output (plus, when supplied, a deterministic resolver) -- calling
    evaluate() twice in a row with nothing changed in between always
    returns an identical result.
    """

    def __init__(
        self,
        guard_service: LLMAgentTaskRecoveryGuardService = None,
        risk_level_resolver=None,
    ):
        self._guard_service = guard_service if guard_service is not None else LLMAgentTaskRecoveryGuardService()
        self._risk_level_resolver = risk_level_resolver

    def evaluate(self, task_id: str, recovery_plan: AgentTaskFailureRecoveryPlan) -> AgentTaskRecoveryGuardEvaluation:
        """Validate recovery_plan through Commit #1's own guard, then
        collapse the result into one allow/deny/review decision.

        Raises:
            InvalidAgentTaskRecoveryGuardError: Propagated, not wrapped,
                from LLMAgentTaskRecoveryGuardService.validate() if
                task_id/recovery_plan is malformed
            InvalidAgentTaskRecoveryGuardEvaluationError: If the optional
                risk_level_resolver returns a value that is not one of
                backend.agent_policy_risk_assessment.LEVELS and not None
        """
        guard_result = self._guard_service.validate(task_id, recovery_plan)

        missing = sorted(_applicable_conditions(guard_result.recommended_action) - set(guard_result.checked_conditions))
        review_reasons = list(guard_result.warnings) + [
            f"condition {name!r} was never verified (no collaborator was supplied to the guard)"
            for name in missing
        ]

        if guard_result.violations:
            decision = DENY
            reason = (
                f"denied: {len(guard_result.violations)} blocking violation(s) found: "
                + "; ".join(guard_result.violations)
            )
        elif review_reasons:
            decision = REVIEW
            reason = (
                f"requires review: {len(review_reasons)} condition(s) need attention: "
                + "; ".join(review_reasons)
            )
        else:
            decision = ALLOW
            reason = "allowed: every applicable condition was verified, with no violations or warnings"

        return AgentTaskRecoveryGuardEvaluation(
            task_id=task_id,
            recommended_action=guard_result.recommended_action,
            decision=decision,
            risk_level=self._resolve_risk_level(task_id, recovery_plan, guard_result),
            blocking_rules=guard_result.violations,
            warnings=tuple(review_reasons),
            reason=reason,
        )

    def _resolve_risk_level(self, task_id, recovery_plan, guard_result):
        if self._risk_level_resolver is None:
            return None
        risk_level = self._risk_level_resolver(task_id, recovery_plan, guard_result)
        if risk_level is not None and risk_level not in LEVELS:
            raise InvalidAgentTaskRecoveryGuardEvaluationError(
                f"risk_level_resolver returned {risk_level!r}, which is not one of {sorted(LEVELS)} (or None)"
            )
        return risk_level
