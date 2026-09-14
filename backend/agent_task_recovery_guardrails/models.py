from dataclasses import dataclass
from typing import Optional


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
