from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

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


@dataclass(frozen=True)
class AgentTaskRecoveryPreflight:
    """LLMAgentTaskRecoveryPreflightStore.save()'s durable, persisted
    snapshot of one Commit #3 AgentTaskRecoveryPreflightResult -- never a
    second orchestration or a new storage framework (Rule: "Persist
    preflight results, not task state"; "Do not invent a new storage
    framework"): this is a plain record of what Commit #3 already decided,
    never itself re-derived, re-planned, or re-evaluated.

    Deliberately narrower than AgentTaskRecoveryPreflightResult -- carries
    exactly the fields the goal names (task_id, preflight_id, plan,
    decision, blocking_reasons, warnings, checked_at), never the full
    Commit #2 guard_result object: decision/blocking_reasons/warnings are
    already that object's own most useful extract (verbatim, on the
    Commit #3 result this is built from), so persisting the whole
    AgentTaskRecoveryGuardEvaluation too would only duplicate the same
    facts a second way.

    plan is the real, already-small AgentTaskFailureRecoveryPlan object
    (never merely a summary) -- unlike an LLM response or task content,
    a recovery plan has no large-payload concern of its own to guard
    against, so embedding it directly (the same "embed the real object
    verbatim" precedent backend.agent_task_event_analytics' own Commit #7
    AgentTaskRecoveryEffectiveness.attempts already establishes for a
    comparable case) is more useful than inventing a lossy reference
    scheme. None exactly when Commit #3 itself reported a planning
    failure (plan=None on the source result) -- never fabricated.

    preflight_id is this record's own fresh identity (Rule: "Saving the
    same preflight must be idempotent where existing IDs allow it" --
    since neither Commit #1/#2/#3 mint an id of their own a save() could
    reuse, a new uuid4 is generated here exactly once per genuinely new
    save, the same "no existing id to reuse, so mint a small, local one"
    precedent backend.agent_task_state_history.TaskTransitionRecord.
    transition_id already establishes for a comparable case). A repeat
    save() of equivalent content instead returns the EXISTING record's
    own preflight_id unchanged, never generating a second one for the
    same evidence.

    Never updated or deleted once recorded (Rule: "Preserve the original
    decision; never silently overwrite history") -- the same append-only
    discipline backend.agent_task_state_history.TaskTransitionRecord and
    backend.agent_policy_history.LLMAgentPolicyChange already establish
    elsewhere in this repository.
    """

    task_id: str
    plan: Optional[AgentTaskFailureRecoveryPlan]
    decision: str
    blocking_reasons: tuple
    warnings: tuple
    checked_at: datetime
    preflight_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["checked_at"] = self.checked_at.isoformat()
        data["blocking_reasons"] = list(self.blocking_reasons)
        data["warnings"] = list(self.warnings)
        if self.plan is not None:
            data["plan"]["blocking_conditions"] = list(self.plan.blocking_conditions)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryPreflight":
        payload = dict(data)
        value = payload.get("checked_at")
        if isinstance(value, str):
            payload["checked_at"] = datetime.fromisoformat(value)
        payload["blocking_reasons"] = tuple(payload.get("blocking_reasons") or ())
        payload["warnings"] = tuple(payload.get("warnings") or ())
        plan_data = payload.get("plan")
        if plan_data is not None:
            plan_payload = dict(plan_data)
            plan_payload["blocking_conditions"] = tuple(plan_payload.get("blocking_conditions") or ())
            payload["plan"] = AgentTaskFailureRecoveryPlan(**plan_payload)
        return cls(**payload)


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightFreshness:
    """LLMAgentTaskRecoveryPreflightFreshnessService.check()'s complete,
    read-only verdict on whether a Commit #4 AgentTaskRecoveryPreflight is
    still trustworthy -- never a second cache/freshness framework (Rule:
    "Do not invent another cache/freshness framework") and never a second
    guard evaluation (Rule: "Do not duplicate Commit #1 guard checks"):
    this service only ever compares a handful of specific, already-
    existing reference facts (current event-sourced task state, the
    current authoritative failure, and whichever of the stored plan's own
    action-relevant conditions have a real existing collaborator to
    re-check) against what the stored preflight itself recorded or
    implied -- it never re-runs Commit #1's own ALLOW/DENY/REVIEW
    machinery a second time.

    is_fresh is exactly `not stale_reasons` -- the same "collect every
    reason, never stop at the first" discipline every comparable result
    in this project already establishes.

    stale_reasons includes not only evidence of an actual CHANGE, but
    also every applicable-but-unverifiable comparison (Rule: "Never
    silently treat missing evidence as fresh" -- the same discipline
    Commit #2's own "never silently convert an unknown condition into
    allow" already establishes for a structurally identical problem): a
    condition relevant to the stored plan's own recommended_action that
    this service has no collaborator to actually re-check is reported as
    its own stale_reasons entry, never silently skipped in a way that
    would let is_fresh default to True.

    checked_references names every reference this call ACTUALLY compared
    (never a condition that was merely applicable-but-unverifiable, which
    lives in stale_reasons instead) -- the same "only claim what was
    genuinely checked" discipline Commit #1's own checked_conditions
    already establishes.

    A stored preflight's own checked_at timestamp is used analytically,
    as the boundary for reconstructing what the task's state WAS at
    preflight time (via a time-bounded replay), never as a naive
    age/TTL check on its own (Rule: "If the repository already has
    version/revision mechanisms, use those instead of timestamps alone"
    -- this repository's own append-only event log already IS a
    revision mechanism; comparing two point-in-time reconstructions of it
    is more precise than treating "old" as inherently unsafe). A merely
    OLD preflight whose task state, plan identity, and relevant
    conditions all still match is still fresh.
    """

    task_id: str
    is_fresh: bool
    stale_reasons: tuple
    checked_references: tuple


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightInvalidation:
    """LLMAgentTaskRecoveryPreflightInvalidationService's durable record
    that one specific Commit #4 AgentTaskRecoveryPreflight (named by its
    own preflight_id) is no longer usable -- never a mutation of that
    original record (Rule: "Never delete the original preflight";
    "preserve the original preflight but mark it unusable"): the
    preflight itself is never touched, rewritten, or removed from Commit
    #4's own store; this is a SEPARATE, additive fact about it, the same
    "mark unusable via a separate record, never by rewriting the
    original" discipline backend.agent_task_queue_dead_letter.
    DeadLetterEntry already establishes for a comparable case (a task is
    never deleted or edited when dead-lettered -- a second, additive
    record says so instead).

    One record per preflight_id (Rule: "Already-invalid preflights remain
    idempotently invalid"): the service layer checks for an existing
    record before ever creating a new one, the same idempotent-by-key
    convention backend.agent_task_queue_dead_letter.LLMAgentTaskDeadLetterService.
    dead_letter() already establishes ("if task_id is already dead-
    lettered, returns that existing entry unchanged").

    previous_decision is exactly the invalidated preflight's own
    `decision` (ALLOW/DENY/REVIEW), captured at invalidation time -- pure
    audit context, "what did we used to think before this was marked
    unusable," never itself re-evaluated or acted upon.
    """

    task_id: str
    preflight_id: str
    reason: str
    previous_decision: str
    invalidated_at: datetime
    invalidation_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["invalidated_at"] = self.invalidated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryPreflightInvalidation":
        payload = dict(data)
        value = payload.get("invalidated_at")
        if isinstance(value, str):
            payload["invalidated_at"] = datetime.fromisoformat(value)
        return cls(**payload)


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightInvalidationResult:
    """LLMAgentTaskRecoveryPreflightInvalidationService.invalidate()/
    invalidate_if_stale()'s complete, read-only report of task_id's own
    preflight-invalidation status right now.

    preflight_id is None exactly when task_id has no stored preflight at
    all (Rule: "missing preflight handled cleanly" -- reported honestly,
    never an error and never fabricated). is_invalid is False both when
    no preflight exists at all and when one exists but was never (and,
    for invalidate_if_stale(), is not currently) found invalid --
    invalidated_at/reason/previous_decision are then all None, the same
    "unknown/inapplicable stays None, never guessed" discipline this
    entire project already establishes everywhere.

    Idempotent by construction (Rule: "repeated invalidation is
    idempotent"): calling invalidate()/invalidate_if_stale() again for a
    preflight_id already carrying an AgentTaskRecoveryPreflightInvalidation
    record returns that SAME existing record's own reason/invalidated_at/
    previous_decision, never a freshly re-derived one.
    """

    task_id: str
    preflight_id: Optional[str]
    is_invalid: bool
    invalidated_at: Optional[datetime]
    reason: Optional[str]
    previous_decision: Optional[str]
