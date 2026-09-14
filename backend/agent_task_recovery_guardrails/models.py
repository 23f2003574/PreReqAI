from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from backend.agent_task_event_analytics import AgentTaskFailureRecoveryPlan


@dataclass(frozen=True)
class AgentTaskRecoveryGuardResult:
    """LLMAgentTaskRecoveryGuardService.validate()'s complete, read-only
    verdict on whether one already-computed recovery plan is still safe
    to execute right now -- never itself a plan or an execution result
    (Rule: "Read-only; never execute recovery"; "Do not duplicate Commit
    #4 recovery execution").

    allowed is exactly `not violations` -- warnings never affect it, the
    same failed-checks/warnings split
    backend.agent_task_readiness.AgentTaskReadinessResult and
    backend.agent_capability_execution_validation.ExecutionValidationResult
    already keep for a comparable structured result elsewhere in this
    repository. violations collects every blocking reason found, never
    only the first (the same "report every blocking reason instead of
    stopping at the first failure" convention those same result types
    already establish).

    checked_conditions names every condition this call actually evaluated
    (Rule: "Unsupported checks must not be fabricated") -- a condition
    whose own collaborator was not supplied to this service is simply
    absent from this tuple, never silently assumed to have passed.

    recommended_action echoes recovery_plan.recommended_action verbatim,
    so a caller inspecting only this result still knows what was being
    validated.
    """

    task_id: str
    recommended_action: str
    allowed: bool
    violations: tuple
    warnings: tuple
    checked_conditions: tuple


@dataclass(frozen=True)
class AgentTaskRecoveryGuardEvaluation:
    """LLMAgentTaskRecoveryGuardEvaluationService.evaluate()'s coarser,
    structured decision over one Commit #1 AgentTaskRecoveryGuardResult --
    never a second validation framework (Rule: "Do not create another
    validation framework"): every input fact here (violations/warnings/
    checked_conditions) is read straight from that result, and the only
    new judgment this layer makes is collapsing them into one of this
    repository's own existing ALLOW/REVIEW/DENY decision values (Rule:
    "Guardrails remain the source of truth for constraint checks";
    "Reuse existing risk/policy semantics; don't invent categories").

    decision is always exactly one of backend.agent_policy_engine.ALLOW/
    DENY or backend.agent_policy_risk_thresholds.REVIEW -- the same three
    string values backend.agent_policy_risk_decision.RiskDecision.decision
    already uses for a *different*, scope_id-scoped domain; this commit
    reuses the same three constants verbatim rather than defining a
    fourth, parallel vocabulary for what is conceptually the same
    tri-state verdict. DENY whenever Commit #1 found any real, evidence-
    backed violation (a hard constraint); REVIEW whenever nothing is
    outright blocking but either Commit #1 itself warned about something,
    or a condition applicable to this plan's own recommended_action was
    never actually checked at all (Rule: "Never silently convert an
    unknown condition into 'allow'" -- an unverified condition is treated
    as "needs a human to look," never as a free pass); ALLOW only when
    every applicable condition was positively verified with nothing to
    report.

    risk_level is populated ONLY when an optional risk_level_resolver was
    supplied to the evaluation service AND it actually returned a value
    (Rule: "risk_level only if an existing risk model supports it") --
    None otherwise. When populated, it is always one of backend.
    agent_policy_risk_assessment.LEVELS (LOW/MEDIUM/HIGH/CRITICAL), this
    repository's own one canonical severity vocabulary, reused verbatim
    -- this service enforces that constraint itself (Rule: "don't invent
    categories") rather than trusting the resolver's own output blindly.

    blocking_rules is exactly Commit #1's own `violations`, carried
    through unchanged -- this layer never re-derives, renames, or
    summarizes an individual violation.

    warnings is Commit #1's own `warnings` plus one explicit entry per
    applicable-but-unverified condition -- both are "worth a human's
    attention, but not blocking" facts, kept together in one place since
    both drive the exact same REVIEW outcome.

    reason is a single, human-readable synthesis of the fields above --
    always built from data already on this same result, never a generic
    or invented explanation.
    """

    task_id: str
    recommended_action: str
    decision: str
    risk_level: Optional[str]
    blocking_rules: tuple
    warnings: tuple
    reason: str


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightResult:
    """LLMAgentTaskRecoveryPreflightService.run()/run_plan()'s single,
    combined snapshot of "what would happen right now if this recovery
    plan were executed" -- never itself a second validation/policy layer
    (Rule: "Do not invent another validation/policy layer"): every fact
    here is read straight from Commit #1's own
    LLMAgentTaskEventFailureRecoveryPlanner.plan() and Commit #2's own
    LLMAgentTaskRecoveryGuardEvaluationService.evaluate() -- this service
    only ever bundles their two outputs into one convenient result, never
    re-deriving or re-checking anything either of them already decided.

    plan is None exactly when recovery planning itself failed (Rule: "If
    planning fails, report that failure instead of fabricating a plan")
    -- guard_result is then also None, since nothing exists to evaluate;
    decision is still always one of backend.agent_policy_engine.ALLOW/DENY
    or backend.agent_policy_risk_thresholds.REVIEW (Rule: "don't invent
    new status enums if existing ones fit") -- DENY, since a recovery that
    cannot even be planned is exactly as unsafe to proceed with as one a
    real guard violation blocks, and blocking_reasons then names the
    planning failure itself.

    decision/blocking_reasons/warnings are guard_result.decision/
    blocking_rules/warnings verbatim whenever guard_result exists (Rule:
    "Reuse Commit #2 rather than duplicating guard evaluation") -- this
    service never re-classifies, re-weighs, or overrides Commit #2's own
    verdict.

    checked_at is the one field allowed to vary between two otherwise-
    identical calls (Rule: "Deterministic apart from repository-standard
    timestamps") -- it is a plain wall-clock record of when this preflight
    ran, accepting an optional `now` the same way every other timestamped
    service in this repository already does, never itself influencing
    plan/guard_result/decision.
    """

    task_id: str
    plan: Optional[AgentTaskFailureRecoveryPlan]
    guard_result: Optional[AgentTaskRecoveryGuardEvaluation]
    decision: str
    blocking_reasons: tuple
    warnings: tuple
    checked_at: datetime
