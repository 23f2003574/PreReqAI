from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from backend.agent_task_event_analytics import AgentTaskFailureRecoveryPlan
from backend.agent_task_queue_retry_eligibility import RetryEligibilityResult
from backend.agent_task_readiness import AgentTaskReadinessCheck, AgentTaskReadinessResult


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionSnapshot:
    """LLMAgentTaskRecoveryExecutionPreconditionSnapshotService.capture()'s
    durable, point-in-time baseline of everything known about task_id
    immediately before its exact, ACTIVE authorization_id would be handed
    to backend.agent_task_event_analytics.LLMAgentTaskFailureRecoveryService.
    execute_plan() -- a distinct boundary from backend.
    agent_task_recovery_preflight_dependency_snapshots (which captures the
    dependency graph a SCHEDULE was prepared against, before execution was
    ever authorized): this snapshot exists to answer "what was actually
    true the instant execution was about to happen," never a second
    dependency-graph or scheduling snapshot.

    Bound to the exact (task_id, authorization_id) capture() was called
    for (Rule: "Bind snapshot to the exact authorization and recovery
    plan") -- preflight_id/approval_id/authorization_status are read
    straight off backend.agent_task_recovery_guardrails' own
    AgentTaskRecoveryPreflightAuthorization record for that exact
    authorization_id, never merely trusted from the caller. recovery_plan
    is the exact backend.agent_task_event_analytics.AgentTaskFailureRecoveryPlan
    embedded in that authorization's own bound preflight (read via
    backend.agent_task_recovery_guardrails' own LLMAgentTaskRecoveryPreflightStore),
    embedded verbatim -- never a second planning/execution decision (Rule:
    "Do not execute, authorize, schedule, or mutate recovery").

    task_state/retry_eligibility/readiness capture only the state actually
    available in the repository through whichever optional collaborators
    were supplied (Rule: "Capture only state actually available in the
    repository") -- each is None when its own collaborator was never
    wired, never fabricated. readiness's own checks already cover both
    dependency readiness and applicable policy state (backend.
    agent_task_readiness.LLMAgentTaskReadinessService.check() already
    folds a "policy" check alongside its "dependencies" one -- Rule: "Do
    not invent a second policy engine," honored by reading that one
    existing answer rather than a second, independent policy/risk read).

    Immutable once recorded (Rule: "Immutable after creation") -- a frozen
    dataclass, and the underlying store this class is persisted through
    has no update()/delete() at all, only save()/get()/list_for_task(),
    the same append-only discipline backend.
    agent_task_recovery_preflight_dependency_snapshots' own
    AgentTaskRecoveryPreflightDependencySnapshot already establishes.
    """

    task_id: str
    authorization_id: str
    preflight_id: str
    approval_id: str
    authorization_status: str
    task_state: Optional[str]
    recovery_plan: Optional[AgentTaskFailureRecoveryPlan]
    retry_eligibility: Optional[RetryEligibilityResult]
    readiness: Optional[AgentTaskReadinessResult]
    captured_at: datetime
    snapshot_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["captured_at"] = self.captured_at.isoformat()
        if self.recovery_plan is not None:
            data["recovery_plan"]["blocking_conditions"] = list(self.recovery_plan.blocking_conditions)
        if self.retry_eligibility is not None and self.retry_eligibility.next_eligible_at is not None:
            data["retry_eligibility"]["next_eligible_at"] = self.retry_eligibility.next_eligible_at.isoformat()
        if self.readiness is not None:
            data["readiness"]["blocking_reasons"] = list(self.readiness.blocking_reasons)
            data["readiness"]["warnings"] = list(self.readiness.warnings)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryExecutionPreconditionSnapshot":
        payload = dict(data)

        value = payload.get("captured_at")
        if isinstance(value, str):
            payload["captured_at"] = datetime.fromisoformat(value)

        plan_data = payload.get("recovery_plan")
        if plan_data is not None:
            plan_payload = dict(plan_data)
            plan_payload["blocking_conditions"] = tuple(plan_payload.get("blocking_conditions") or ())
            payload["recovery_plan"] = AgentTaskFailureRecoveryPlan(**plan_payload)

        retry_data = payload.get("retry_eligibility")
        if retry_data is not None:
            retry_payload = dict(retry_data)
            next_eligible = retry_payload.get("next_eligible_at")
            if isinstance(next_eligible, str):
                retry_payload["next_eligible_at"] = datetime.fromisoformat(next_eligible)
            payload["retry_eligibility"] = RetryEligibilityResult(**retry_payload)

        readiness_data = payload.get("readiness")
        if readiness_data is not None:
            readiness_payload = dict(readiness_data)
            readiness_payload["checks"] = [
                AgentTaskReadinessCheck(**check) for check in readiness_payload.get("checks") or []
            ]
            payload["readiness"] = AgentTaskReadinessResult(**readiness_payload)

        return cls(**payload)


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionFieldChange:
    """One field whose captured value no longer matches compare()'s own
    fresh read, named explicitly rather than left for a caller to diff
    the two snapshots' fields itself."""

    field: str
    previous_value: object
    current_value: object


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionSnapshotDiff:
    """LLMAgentTaskRecoveryExecutionPreconditionSnapshotService.compare()'s
    complete, read-only comparison of one persisted snapshot against
    task_id's CURRENT state, right now -- never a second reconciliation
    engine (Rule: "compare() detects changes since capture"), and never
    itself a scheduling/recovery decision (Rule: "Do not execute,
    authorize, schedule, or mutate recovery"): every fact here comes from
    re-reading the same collaborators capture() itself used, nothing more.

    changed is exactly whether any per-field flag below is True (a plain
    OR, never independently computed); a dimension whose own collaborator
    was never wired stays None on both sides and never contributes a
    changed=True. changes names every field that actually differs, with
    both its captured and current value, so a caller never has to
    re-derive what moved from two opaque snapshot objects.
    """

    task_id: str
    snapshot_id: str
    authorization_id: str
    preflight_id: str
    changed: bool
    authorization_status_changed: bool
    task_state_changed: bool
    retry_eligibility_changed: bool
    readiness_changed: bool
    changes: tuple
    current_authorization_status: Optional[str]
    current_task_state: Optional[str]
    current_retry_eligibility: Optional[RetryEligibilityResult]
    current_readiness: Optional[AgentTaskReadinessResult]
    compared_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionValidationResult:
    """LLMAgentTaskRecoveryExecutionPreconditionValidationService.
    validate()'s complete, read-only verdict on whether a Commit #1
    snapshot's captured baseline still holds, right now -- never a
    second policy/dependency/authorization engine (Rule: "Reuse existing
    validators; don't recreate policy/dependency logic"): every blocking
    fact here is read straight from backend.agent_task_recovery_guardrails'
    own already-existing LLMAgentTaskRecoveryPreflightAuthorizationValidationService
    (authorization validity/binding: revoked/superseded/invalidated/
    stale/lapsed-approval/policy-blocked) and
    LLMAgentTaskRecoveryGuardService (task eligibility, plan freshness --
    "authorized recovery action/plan is unchanged", action/policy
    permission, retry/budget limits, dependency readiness, conflicting
    active recovery) -- nothing here re-derives any of their own logic a
    second way.

    Clearly distinguishes harmless changes from execution-blocking ones
    (Rule): `diff` is Commit #1's own, purely informational
    AgentTaskRecoveryExecutionPreconditionSnapshotDiff -- it can be
    `changed=True` (e.g. a dependency resolved, retry eligibility
    improved) while `valid` stays True, since `valid`/`blocking_reasons`
    are derived ONLY from authorization_validation/guard_result, never
    from diff's own booleans. guard_result is None only when the
    snapshot itself captured no recovery_plan to validate (itself then
    an unconditional blocking_reasons entry -- Rule: "Fail closed on
    material state changes").

    valid is exactly `not blocking_reasons`; warnings never affect it,
    the same failed-checks/warnings split every comparable result in
    this repository already keeps.
    """

    task_id: str
    snapshot_id: str
    authorization_id: str
    preflight_id: str
    valid: bool
    blocking_reasons: tuple
    warnings: tuple
    diff: AgentTaskRecoveryExecutionPreconditionSnapshotDiff
    authorization_validation: object
    guard_result: Optional[object]
    validated_at: datetime


# LLMAgentTaskRecoveryExecutionPreconditionDriftService's own drift-category
# vocabulary -- a closed, four-valued scale (Rule: "classify ... into
# existing repository concepts") deliberately graduated between Commit #2's
# own binary valid/blocking_reasons: NONE is exactly "nothing changed at
# all" (diff.changed is False); NON_BLOCKING is a real, observed change that
# Commit #2's own fresh re-validation already confirmed is not currently
# blocking; REQUIRES_REVALIDATION is reserved for a change that is *also*
# not currently blocking but is significant/ambiguous enough (a lifecycle
# move between two live states, a collaborator becoming newly wired/
# unwired between capture and compare) to warrant an operator's or a later
# audit's explicit attention, even though the fresh validators already
# looked; EXECUTION_BLOCKED is exactly whenever Commit #2's own
# validation_result.valid is False -- this class never overrides that
# verdict, only explains it per field (Rule: "Never approve or execute
# recovery itself"; "Base classification only on the existing validation
# diff").
DRIFT_NONE = "none"
DRIFT_NON_BLOCKING = "non_blocking"
DRIFT_REQUIRES_REVALIDATION = "requires_revalidation"
DRIFT_EXECUTION_BLOCKED = "execution_blocked"
DRIFT_CATEGORIES = frozenset({DRIFT_NONE, DRIFT_NON_BLOCKING, DRIFT_REQUIRES_REVALIDATION, DRIFT_EXECUTION_BLOCKED})

# The severity ordering DRIFT_CATEGORIES are combined under -- the overall
# drift category is always the single worst category among all per-field
# items, never merely the last one computed.
_DRIFT_SEVERITY = {DRIFT_NONE: 0, DRIFT_NON_BLOCKING: 1, DRIFT_REQUIRES_REVALIDATION: 2, DRIFT_EXECUTION_BLOCKED: 3}


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionDriftItem:
    """One Commit #1 snapshot field's own drift classification -- `field`/
    `previous_value`/`current_value` are exactly Commit #2's own diff.changes
    entries where one exists (`concern` is this class's own, added mapping
    from that field to the recovery concern it governs -- "authorization",
    "task_eligibility", "retry_budget", or "dependency_and_policy_readiness",
    the same named concerns backend.agent_task_recovery_guardrails.
    LLMAgentTaskRecoveryGuardService.validate() already checks under, never
    a newly-invented taxonomy), plus one synthetic "unclassified" entry
    (`field=None`) only when validation_result reported blocking_reasons
    that no tracked field's own comparison explains (Rule: "Fail closed
    when a material difference cannot be classified safely" -- its own
    category is always EXECUTION_BLOCKED, never guessed softer).

    execution_may_continue is exactly `category != DRIFT_EXECUTION_BLOCKED`
    -- true for NONE/NON_BLOCKING/REQUIRES_REVALIDATION alike, since a
    REQUIRES_REVALIDATION item, by construction, only ever appears when
    Commit #2's own fresh validation_result.valid is already True (that
    fresh check already ran and did not block it); it is a stronger,
    audit-worthy flag layered on top of "not currently blocking," never a
    softer form of "blocked."
    """

    field: Optional[str]
    concern: str
    category: str
    previous_value: object
    current_value: object
    reason: str
    execution_may_continue: bool


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionDriftResult:
    """LLMAgentTaskRecoveryExecutionPreconditionDriftService.classify()'s
    complete, read-only drift classification for one Commit #1 snapshot_id
    -- never a second validation engine (Rule: "Do not create another
    validation engine"): `validation` is Commit #2's own
    AgentTaskRecoveryExecutionPreconditionValidationResult, embedded
    verbatim, and every `items` entry is derived only from its own
    `diff`/`blocking_reasons` -- nothing here re-derives policy, dependency,
    retry-budget, or authorization logic a second way.

    category is the single worst (highest-severity) category among `items`
    (NONE when there are none at all); execution_may_continue is exactly
    `validation.valid`, so it can never disagree with the validator it was
    computed from, whatever the per-item detail says (Rule: "Never approve
    or execute recovery itself" -- this class only explains a verdict
    Commit #2 already reached, never substitutes its own).

    Preserves enough detail for later audit/recovery analysis (Rule):
    `items` names every changed field with its own previous/current value,
    concern, category, and reason; `blocking_reasons`/`warnings` are Commit
    #2's own fields, carried through unchanged, so nothing about why
    execution is or is not blocked is ever only inferable from `category`
    alone.
    """

    task_id: str
    snapshot_id: str
    authorization_id: str
    preflight_id: str
    category: str
    execution_may_continue: bool
    items: tuple
    blocking_reasons: tuple
    warnings: tuple
    validation: AgentTaskRecoveryExecutionPreconditionValidationResult
    classified_at: datetime


# LLMAgentTaskRecoveryExecutionPreconditionRevalidationService's own outcome
# vocabulary -- the same REUSED/REPLACED/FAILED *shape* backend.
# agent_task_recovery_preflight_dependency_snapshots'
# AgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationResult already
# establishes for a comparable "reuse an existing valid record, or rebuild
# it, or honestly report a rebuild that still fails" decision -- defined
# locally rather than imported, since that package's own revalidation is
# scoped to dependency-graph trust, a genuinely different domain (Rule
# elsewhere in this project: reuse conventions/shapes across domains, never
# the tightly-coupled classes themselves). REUSED: no blocking drift existed
# at all, or an already-rebuilt snapshot for the same authorization is still
# current -- returned unchanged, never a copy. REPLACED: a fresh snapshot
# was captured and it is now eligible. REVALIDATION_FAILED: a fresh snapshot
# was captured but it is STILL blocked -- reported honestly, never retried
# in a loop or fabricated as eligible. There is no "MISSING" value: an
# unknown snapshot_id is raised (InvalidAgentTaskRecoveryExecutionPrecondition
# RevalidationError), the same "not found is an error" convention Commits
# #1-#3 of this series already establish for themselves.
REVALIDATION_REUSED = "reused"
REVALIDATION_REPLACED = "replaced"
REVALIDATION_FAILED = "failed"
REVALIDATION_ACTIONS = frozenset({REVALIDATION_REUSED, REVALIDATION_REPLACED, REVALIDATION_FAILED})


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionRevalidationResult:
    """LLMAgentTaskRecoveryExecutionPreconditionRevalidationService.
    revalidate()'s complete report -- never a second snapshot/validation
    system (Rule: "Do not create another snapshot or validation system"):
    old_drift/new_drift are exactly Commit #3's own
    AgentTaskRecoveryExecutionPreconditionDriftResult objects, carried
    through unchanged, and new_snapshot_id (when not equal to
    old_snapshot_id) is a genuinely new Commit #1 snapshot, captured
    through Commit #1's own capture() -- never a second capture mechanism.

    new_snapshot_id equals old_snapshot_id exactly when action is REUSED
    with no rebuild at all (Rule: "If no blocking drift exists, return the
    existing snapshot" -- never a copy); it is a DIFFERENT, already-
    existing snapshot_id when action is REUSED because an earlier rebuild
    already produced a still-current one (Rule: "Idempotent when current
    state already has an equivalent valid snapshot"); it is a fresh
    snapshot_id for REPLACED/REVALIDATION_FAILED alike (Rule: "a fresh
    snapshot was created, but it ALSO failed trust" -- the same honest
    "rebuilt but still bad" reporting, never silently discarded); it is
    None only when no rebuild could even be attempted at all (Rule: "Fail
    closed if current state cannot be safely captured"; "Never silently
    preserve an invalid authorization" -- no ACTIVE authorization exists
    for the task's current preflight to bind a rebuild against).

    eligible is exactly the returned snapshot's own execution_may_continue
    (new_drift.execution_may_continue when new_drift is not None, else
    False) -- never independently decided, and never used to authorize or
    execute anything itself (Rule: "Do not execute recovery" -- this class
    only ever calls capture()/classify(), both already read-only or
    write-once-immutable).

    Complete history is preserved implicitly (Rule): Commit #1's own
    snapshot store is append-only (nothing here ever deletes or rewrites
    old_snapshot_id's own record), and old_snapshot_id/new_snapshot_id
    together are this result's own explicit link between the superseded
    and superseding snapshot.
    """

    task_id: str
    old_snapshot_id: str
    new_snapshot_id: Optional[str]
    action: str
    old_drift: AgentTaskRecoveryExecutionPreconditionDriftResult
    new_drift: Optional[AgentTaskRecoveryExecutionPreconditionDriftResult]
    eligible: bool
    reason: Optional[str]
    revalidated_at: datetime


# LLMAgentTaskRecoveryExecutionPreconditionApprovalReconciliationService's
# own verdict vocabulary -- a closed, three-valued scale describing whether
# an EXISTING backend.agent_task_recovery_guardrails.
# AgentTaskRecoveryPreflightApproval record still applies, never a fourth
# approval store or a new status value written onto that record itself
# (Rule: "Do not create another approval system"; "Keep old approval
# history immutable"): PRESERVED is exactly "the original approval is
# APPROVED, and Commit #4's own revalidate() found nothing blocking at all
# for the exact snapshot/preflight/authorization it was granted against."
# REVOKED is exactly "Commit #4 could not resolve any active authorization
# at all" (its own fail-closed REVALIDATION_FAILED-with-no-snapshot case).
# REQUIRES_REVIEW is every other case -- material drift, a rebuilt/
# different preflight, a changed recommended action, or an approval that
# was never granted (missing/pending/rejected) in the first place -- Rule:
# "Never automatically approve a materially changed recovery" means this
# class only ever reports REQUIRES_REVIEW here; it never calls approve()
# itself.
RECONCILED_PRESERVED = "preserved"
RECONCILED_REQUIRES_REVIEW = "requires_review"
RECONCILED_REVOKED = "revoked"
APPROVAL_RECONCILIATION_STATES = frozenset({RECONCILED_PRESERVED, RECONCILED_REQUIRES_REVIEW, RECONCILED_REVOKED})


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionApprovalReconciliationResult:
    """LLMAgentTaskRecoveryExecutionPreconditionApprovalReconciliationService.
    reconcile()'s complete, read-only verdict on whether task_id's existing
    backend.agent_task_recovery_guardrails.AgentTaskRecoveryPreflightApproval
    still applies to the CURRENT execution-precondition state -- never a
    second approval/authorization framework (Rule: "Reuse existing
    approval/authorization state transitions"): `revalidation` is Commit
    #4's own AgentTaskRecoveryExecutionPreconditionRevalidationResult,
    embedded verbatim, and `previous_approval`/`current_approval` are
    backend.agent_task_recovery_guardrails' own AgentTaskRecoveryPreflightApproval
    records, read straight off its own store -- nothing here writes to
    that store, ever (Rule: "Keep old approval history immutable"; "Never
    automatically approve a materially changed recovery").

    previous_snapshot_id/previous_preflight_id/previous_authorization_id
    are exactly the (task_id, snapshot_id) reconcile() was called with,
    and what that snapshot was itself bound to; current_snapshot_id/
    current_preflight_id/current_authorization_id are Commit #4's own
    new_snapshot_id and whatever it is bound to -- all three current_*
    fields are None together exactly when state is REVOKED (Commit #4
    could not resolve any active authorization to rebuild against at
    all).

    Idempotent by composition (Rule): every field here is derived purely
    from Commit #4's own already-idempotent revalidate() plus a read-only
    approval_service.get() -- calling reconcile() twice in a row with
    nothing else changed always returns an identical result.
    """

    task_id: str
    previous_snapshot_id: str
    current_snapshot_id: Optional[str]
    previous_preflight_id: str
    current_preflight_id: Optional[str]
    previous_authorization_id: str
    current_authorization_id: Optional[str]
    state: str
    previous_approval: Optional[object]
    current_approval: Optional[object]
    revalidation: AgentTaskRecoveryExecutionPreconditionRevalidationResult
    reason: str
    reconciled_at: datetime


# LLMAgentTaskRecoveryExecutionPreconditionDecisionService's own verdict
# vocabulary -- named distinctly from backend.agent_policy_engine.ALLOW/DENY
# (a different decision space entirely: that one is a single policy-rule
# verdict, this one composes three whole precondition services) to avoid
# any reader confusing the two despite the shared English word. BLOCK is
# whenever Commit #2's own validation_result.valid is False, or Commit #3's
# own drift.category is DRIFT_EXECUTION_BLOCKED (the same underlying fact,
# checked both ways for explicitness -- Rule: "invalid/unsafe precondition
# -> block"). REVIEW covers two independent, non-blocking signals (Rule:
# "material drift requiring human review -> review"; "approval no longer
# applicable -> review"): Commit #3's own DRIFT_REQUIRES_REVALIDATION, or
# Commit #5's own reconciliation.state not being RECONCILED_PRESERVED.
# ALLOW is reported only when none of the above apply at all.
EXECUTION_DECISION_ALLOW = "allow"
EXECUTION_DECISION_REVIEW = "review"
EXECUTION_DECISION_BLOCK = "block"
EXECUTION_DECISIONS = frozenset({EXECUTION_DECISION_ALLOW, EXECUTION_DECISION_REVIEW, EXECUTION_DECISION_BLOCK})


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionDecision:
    """LLMAgentTaskRecoveryExecutionPreconditionDecisionService.decide()'s
    single, canonical, read-only verdict on whether task_id's exact
    snapshot_id may proceed to recovery execution right now -- never a
    second precondition engine (Rule: "Do not invent new infrastructure or
    duplicate their rules"): validation_result/drift_classification/
    approval_reconciliation are exactly Commits #2/#3/#5's own result
    objects, embedded verbatim -- decision/reason/blocking_conditions are
    the only new judgment this class adds, and that judgment is a pure,
    deterministic function of those three objects' own already-computed
    fields, nothing re-derived a second way.

    authorization_id is the snapshot's own bound authorization_id (Commit
    #1's own snapshot.authorization_id) whenever the snapshot could be
    found at all -- not merely the caller-supplied value, so a caller who
    passed None still gets a fully identified decision back; when a
    caller-supplied authorization_id does not match the snapshot's own
    binding, that mismatch is itself fail-closed to BLOCK (Rule: "Fail
    closed if required evidence is unavailable" applied to identity, not
    only presence).

    validation_result/drift_classification/approval_reconciliation are
    None only when they could not even be computed at all (the named
    snapshot_id does not exist, or a composed service raised) -- Rule:
    "Fail closed if required evidence is unavailable" means decision is
    always BLOCK whenever any of them is None, never ALLOW/REVIEW guessed
    from partial evidence.

    Never itself executes, authorizes, schedules, or approves anything
    (Rule: "Never execute recovery from this service; it is the canonical
    decision boundary only") -- decide() only ever calls other services'
    own read methods.
    """

    task_id: str
    snapshot_id: str
    authorization_id: Optional[str]
    decision: str
    reason: str
    blocking_conditions: tuple
    warnings: tuple
    validation_result: Optional[AgentTaskRecoveryExecutionPreconditionValidationResult]
    drift_classification: Optional[AgentTaskRecoveryExecutionPreconditionDriftResult]
    approval_reconciliation: Optional[AgentTaskRecoveryExecutionPreconditionApprovalReconciliationResult]
    created_at: datetime
    decision_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionDecisionComparison:
    """LLMAgentTaskRecoveryExecutionPreconditionDecisionComparisonService.
    compare()'s complete, read-only diff between two Commit #7-persisted
    AgentTaskRecoveryExecutionPreconditionDecision records -- never a
    second diff engine (Rule: "Do not invent infrastructure or duplicate
    snapshot/validation logic"): every field here is a plain comparison of
    two already-persisted decisions' own fields, read straight through
    Commit #7's own store -- nothing here reruns validate()/classify()/
    reconcile()/decide().

    decision_id/other_decision_id echo compare()'s own arguments exactly
    (other_decision_id resolved to the task's chronologically previous
    decision when the caller omitted it); earlier_decision_id/
    later_decision_id are the same two decisions ordered by their own
    created_at instead, since decision_transition/changed_fields/added-
    removed-* all describe a FROM -> TO change and must mean the same
    thing regardless of which argument position the caller happened to
    pass each decision_id in (Rule: "Preserve deterministic output
    ordering").

    changed_fields reuses Commit #2's own AgentTaskRecoveryExecutionPreconditionFieldChange
    shape verbatim (never a second field-change type), one entry per
    field that actually differs, sorted by field name; a field that did
    not change contributes no entry at all. changed is exactly whether
    changed_fields/added_*/removed_* is non-empty; comparing a decision
    against itself always produces changed=False with every tuple empty.
    """

    task_id: str
    decision_id: str
    other_decision_id: str
    earlier_decision_id: str
    later_decision_id: str
    decision_transition: str
    eligibility_changed: bool
    snapshot_changed: bool
    authorization_changed: bool
    drift_classification_changed: bool
    approval_reconciliation_changed: bool
    added_blocking_conditions: tuple
    removed_blocking_conditions: tuple
    added_warnings: tuple
    removed_warnings: tuple
    changed_fields: tuple
    changed: bool
    compared_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionDecisionTransition:
    """LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService.
    analyze()'s structured explanation of how execution eligibility moved
    between two Commit #7-persisted decisions -- never a second diff
    engine (Rule: "Do not duplicate comparison logic"): every field below
    is read straight off Commit #8's own
    AgentTaskRecoveryExecutionPreconditionDecisionComparison, plus one
    new classification (transition_type/requires_attention) computed only
    from that comparison's own already-computed fields.

    transition_type is exactly f"{from_decision}_to_{to_decision}" -- one
    of the nine allow/review/block combinations named in the goal, never
    re-derived from raw evidence. eligibility_changed is Commit #8's own
    comparison.eligibility_changed, unchanged.

    requires_attention is true exactly when severity worsened (allow <
    review < block, so allow->review/block or review->block) or a
    genuinely NEW blocking condition appeared even without the coarse
    category moving (e.g. review->review with a different blocker) --
    never true for an improving or unchanged transition, since "needs
    attention" means something got worse, not better.
    """

    task_id: str
    from_decision_id: str
    to_decision_id: str
    from_decision: str
    to_decision: str
    transition_type: str
    eligibility_changed: bool
    blocking_conditions_added: tuple
    blocking_conditions_removed: tuple
    warnings_added: tuple
    warnings_removed: tuple
    material_changes: tuple
    requires_attention: bool
    analyzed_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionDecisionHistory:
    """LLMAgentTaskRecoveryExecutionPreconditionDecisionHistoryService.
    get_history()'s complete, read-only view of one task's own decision
    history -- never a second persistence/comparison engine (Rule): every
    entry in `decisions` and `transitions` is read straight through
    Commit #7's own store and Commit #9's own analyze(), nothing here
    recomputes validation/drift/authorization/approval state.

    `decisions` is the (possibly limit-truncated) chronological slice
    get_history() was actually asked for; `decision_count`/
    `counts_by_decision`/`transitions`/`eligibility_change_count`/
    `review_or_block_transition_count` are always computed over the
    task's COMPLETE history regardless of `limit` -- limiting only ever
    trims which raw records are returned for display, never the
    aggregate facts describing the task's real, complete history.

    `transitions` holds one Commit #9 AgentTaskRecoveryExecutionPreconditionDecisionTransition
    per consecutive pair in the complete history, oldest pair first (N
    decisions produce N-1 transitions, 0 for an empty or single-decision
    history). current_eligible is exactly `latest_decision.decision ==
    EXECUTION_DECISION_ALLOW`, False when there is no decision at all.
    """

    task_id: str
    decisions: tuple
    first_decision: Optional[object]
    latest_decision: Optional[object]
    decision_count: int
    counts_by_decision: dict
    transitions: tuple
    eligibility_change_count: int
    review_or_block_transition_count: int
    current_eligible: bool
    first_decision_at: Optional[datetime]
    last_decision_at: Optional[datetime]
    generated_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionDecisionAuditRecord:
    """LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService.
    record()'s durable, append-only capture of one Commit #7-persisted
    AgentTaskRecoveryExecutionPreconditionDecision -- never a second audit
    framework (Rule: "Do not invent a new audit framework"): decision/
    snapshot_id/authorization_id/reason/blocking_conditions/warnings are
    that decision's own fields, preserved verbatim (Rule: "Preserve
    enough evidence to reconstruct what decision was being acted upon"),
    never re-derived a second way.

    actor/operation_id are this call's own, purely additive context (who/
    what triggered recording this entry) -- both None when the caller
    supplied neither, never fabricated. Immutable once recorded (Rule:
    "Audit records are append-only; never mutate historical entries"):
    a frozen dataclass, and the underlying store this class is persisted
    through has no update()/delete() at all.
    """

    task_id: str
    decision_id: str
    decision: str
    snapshot_id: str
    authorization_id: Optional[str]
    reason: str
    blocking_conditions: tuple
    warnings: tuple
    actor: Optional[str]
    operation_id: Optional[str]
    recorded_at: datetime
    audit_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionDecisionAuditVerification:
    """LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationService.
    verify()'s complete, read-only verdict on whether one Commit #12 audit
    record still faithfully represents the Commit #7-persisted decision it
    references -- never a second audit/persistence system (Rule: "Do not
    create another audit or persistence system"): every fact here is a
    plain field-by-field comparison between the audit record and the
    decision Commit #7's own store returns for its exact decision_id,
    never a recomputed decision.

    decision_found is False exactly when Commit #7's store no longer has
    any record for the audit's own decision_id -- valid is then always
    False too (Rule: "Fail closed when the referenced decision cannot be
    found"), and mismatches is empty (there is nothing left to compare
    field-by-field), the fact itself carried in `reason`.

    mismatches names every field whose audit-recorded value no longer
    equals the decision's own current value (task_id/snapshot_id/
    authorization_id/decision/reason/blocking_conditions/warnings);
    missing_fields names every required audit field (decision/snapshot_id/
    reason) that is itself blank on the audit record, independent of
    whether the referenced decision could be found at all. valid is
    exactly `decision_found and not mismatches and not missing_fields`.
    """

    task_id: str
    audit_id: str
    decision_id: str
    decision_found: bool
    valid: bool
    mismatches: tuple
    missing_fields: tuple
    reason: Optional[str]
    verified_at: datetime


INTEGRITY_VALID = "valid"
INTEGRITY_INVALID = "invalid"
INTEGRITY_STATUSES = frozenset({INTEGRITY_VALID, INTEGRITY_INVALID})


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionIntegrityResult:
    """LLMAgentTaskRecoveryExecutionDecisionIntegrityService.check()'s
    complete, read-only verdict on whether one Commit #7-persisted
    decision is internally sound -- never a second persistence/audit
    framework (Rule: "Do not create another persistence or audit
    framework"): every issue is found by reading through Commit #7's own
    decision store, Commit #1's own snapshot service, backend.
    agent_task_recovery_guardrails' own authorization service, and
    Commit #12/#13's own audit service/verification -- nothing here
    recomputes the decision itself.

    status is INTEGRITY_INVALID exactly when `issues` is non-empty;
    a missing/task-mismatched decision_id is fail-closed to
    INTEGRITY_INVALID immediately (Rule: "Fail closed on missing critical
    evidence"), with every other check skipped since there is nothing
    left to check against.
    """

    task_id: str
    decision_id: str
    status: str
    issues: tuple
    checked_at: datetime


FRESHNESS_FRESH = "fresh"
FRESHNESS_STALE = "stale"
FRESHNESS_UNKNOWN = "unknown"
FRESHNESS_STATUSES = frozenset({FRESHNESS_FRESH, FRESHNESS_STALE, FRESHNESS_UNKNOWN})


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionStalenessResult:
    """LLMAgentTaskRecoveryExecutionDecisionStalenessService.check()'s
    complete, read-only verdict on whether a Commit #7-persisted decision
    still safely represents CURRENT recovery state -- never a new
    lifecycle/TTL policy (Rule: "Do not invent a new lifecycle policy";
    "Prefer explicit version changes over arbitrary time-based TTLs"):
    every signal is either an explicit identity change (decision_state_version/
    current_state_version -- the decision's own bound snapshot_id vs.
    Commit #1's own latest_for_authorization() snapshot_id for that same
    authorization, right now) or Commit #3's own drift classification of
    the decision's own snapshot_id -- nothing here measures elapsed wall-
    clock time at all.

    UNKNOWN is reported whenever required freshness evidence itself
    cannot be established (Commit #1's own integrity check failed, drift
    classification could not even run, or a compared field's own current
    value cannot be read at all) -- Rule: "Never declare a decision fresh
    when required freshness evidence is unavailable" means UNKNOWN, never
    a guessed FRESH, is the honest answer in that case.

    current_state_version/decision_state_version are both the identity of
    a Commit #1 snapshot (never a fabricated version number this project
    has no real concept of) -- current_state_version is None only when no
    later snapshot could be resolved for the decision's own
    authorization_id at all.
    """

    task_id: str
    decision_id: str
    status: str
    reason: str
    decision_timestamp: datetime
    current_state_version: Optional[str]
    decision_state_version: Optional[str]
    checked_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionCurrentStateEvidence:
    """The small, already-computed evidence bundle
    LLMAgentTaskRecoveryExecutionDecisionFreshnessPolicy.explain() compares
    a decision against -- deliberately just plain values, never a live
    service handle, so the policy itself can stay pure/read-only (Rule:
    "Keep the policy pure/read-only"). current_state_version is Commit
    #1's own latest snapshot_id for the decision's own authorization_id
    (None when it could not be resolved at all -- e.g. the decision itself
    carries no authorization_id); drift_category is Commit #3's own
    category for the decision's snapshot_id; ambiguous is true when any
    compared field's current value could not be safely read at all."""

    current_state_version: Optional[str]
    drift_category: Optional[str]
    ambiguous: bool


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord:
    """LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService.
    record()'s durable, append-only capture of one freshness evaluation --
    never a second audit framework (Rule: "Do not create a second audit
    framework"; same dual-index, append-only shape Commit #12's own
    AgentTaskRecoveryExecutionPreconditionDecisionAuditRecord already
    establishes). freshness_status/freshness_reason/decision_state_version/
    current_state_version are Commit #2's own AgentTaskRecoveryExecutionDecisionStalenessResult
    fields, preserved verbatim.

    revalidated is whether a Commit #4 revalidation_result was given at
    all; revalidation_action is that result's own action
    (REUSED/REPLACED/FAILED) when given, else None.
    replacement_decision_id is that result's own new_decision_id only when
    it names a genuinely DIFFERENT decision than decision_id (a fresh
    replacement actually created) -- None when revalidation reused the
    same decision unchanged, produced no replacement, or was never run at
    all (Rule: "Link old/new decisions when revalidation occurs").
    """

    task_id: str
    decision_id: str
    freshness_status: str
    freshness_reason: str
    decision_state_version: Optional[str]
    current_state_version: Optional[str]
    revalidated: bool
    revalidation_action: Optional[str]
    replacement_decision_id: Optional[str]
    recorded_at: datetime
    audit_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionFreshnessRevalidationResult:
    """LLMAgentTaskRecoveryExecutionDecisionFreshnessRevalidationService.
    revalidate()'s complete report -- never a second decision engine
    (Rule: "Do not create another decision engine"): every write here is
    delegated to an already-existing service (Commit #4-of-the-earlier-
    series' own precondition revalidate(), Commit #6-of-the-earlier-
    series' own decide(), Commit #7-of-the-earlier-series' own decision
    store) -- this class only decides WHETHER a rebuild is needed and
    links the result.

    Reuses the earlier series' own REVALIDATION_REUSED/REVALIDATION_REPLACED/
    REVALIDATION_FAILED vocabulary verbatim (same meaning: REUSED -- the
    old decision was already fresh, or an already-persisted later decision
    is already equivalent and fresh, returned unchanged; REPLACED -- a
    fresh decision was computed and persisted, whatever its own allow/
    review/block value; REVALIDATION_FAILED -- no usable current snapshot
    could be established at all, a process failure, never merely an
    unfavorable new decision).

    new_decision_id equals old_decision_id exactly when action is REUSED
    with no rebuild at all; it is a DIFFERENT, already-persisted
    decision_id when REUSED because an equivalent fresh decision already
    exists; it is a freshly persisted decision_id for REPLACED; it is None
    only for REVALIDATION_FAILED.
    """

    task_id: str
    old_decision_id: str
    new_decision_id: Optional[str]
    action: str
    staleness: AgentTaskRecoveryExecutionDecisionStalenessResult
    old_decision: object
    new_decision: Optional[object]
    reason: Optional[str]
    revalidated_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionDecisionReport:
    """LLMAgentTaskRecoveryExecutionPreconditionDecisionReportingService.
    report()'s compact, structured, task-level operational report -- never
    a second history/aggregation engine (Rule: "Reuse its existing
    transition and aggregation results"; "Do not turn this into
    analytics"): every field is read straight off Commit #10's own
    AgentTaskRecoveryExecutionPreconditionDecisionHistory, nothing here
    recomputes a count, transition, or decision a second way.

    latest_transition/material_changes are Commit #9's own last transition
    in `decision_history.transitions` (None/() when fewer than two
    decisions exist at all); blocking_conditions/warnings are exactly the
    LATEST decision's own fields (the currently relevant ones, not a
    union across history). decision_history is Commit #10's own
    (possibly limit-truncated) `decisions` tuple, carried through
    unchanged.
    """

    task_id: str
    latest_decision: Optional[object]
    latest_decision_at: Optional[datetime]
    current_eligible: bool
    decision_count: int
    counts_by_decision: dict
    transition_count: int
    eligibility_change_count: int
    review_or_block_transition_count: int
    latest_transition: Optional[object]
    material_changes: tuple
    blocking_conditions: tuple
    warnings: tuple
    decision_history: tuple
    generated_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionPreconditionDecisionHistorySummary:
    """summarize()'s compact rollup of one task's own decision history --
    exactly get_history()'s own aggregate fields, minus the raw
    decisions/transitions lists (Rule: "Do not duplicate decision/
    comparison logic" -- summarize() is built ON TOP of get_history(),
    never a second aggregation pass over the store)."""

    task_id: str
    decision_count: int
    counts_by_decision: dict
    eligibility_change_count: int
    review_or_block_transition_count: int
    current_eligible: bool
    latest_decision: Optional[object]
    first_decision_at: Optional[datetime]
    last_decision_at: Optional[datetime]
    generated_at: datetime


FRESHNESS_HISTORY_DECISION_RECORDED = "decision_recorded"
FRESHNESS_HISTORY_FRESH_REUSE = "fresh_reuse"
FRESHNESS_HISTORY_STALE_DETECTED = "stale_detected"
FRESHNESS_HISTORY_INDETERMINATE_DETECTED = "indeterminate_detected"
FRESHNESS_HISTORY_REVALIDATION_REUSED = "revalidation_reused"
FRESHNESS_HISTORY_REVALIDATION_REPLACED = "revalidation_replaced"
FRESHNESS_HISTORY_REVALIDATION_FAILED = "revalidation_failed"
FRESHNESS_HISTORY_EVENT_TYPES = (
    FRESHNESS_HISTORY_DECISION_RECORDED,
    FRESHNESS_HISTORY_FRESH_REUSE,
    FRESHNESS_HISTORY_STALE_DETECTED,
    FRESHNESS_HISTORY_INDETERMINATE_DETECTED,
    FRESHNESS_HISTORY_REVALIDATION_REUSED,
    FRESHNESS_HISTORY_REVALIDATION_REPLACED,
    FRESHNESS_HISTORY_REVALIDATION_FAILED,
)


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionFreshnessHistoryEvent:
    """One entry in LLMAgentTaskRecoveryExecutionDecisionFreshnessHistoryService.
    get_history()'s chronological chain -- either a persisted decision
    (event_type DECISION_RECORDED, sourced from the decision store) or one
    freshness audit record (sourced from Commit #5's own audit trail),
    every field copied verbatim, never recomputed.

    revalidated distinguishes a decision accepted as fresh (False) from
    one that actually went through Commit #4's revalidation (True), even
    when that revalidation merely reused the same decision.
    """

    sequence: int
    event_type: str
    occurred_at: datetime
    decision_id: str
    freshness_status: Optional[str]
    freshness_reason: Optional[str]
    decision_state_version: Optional[str]
    current_state_version: Optional[str]
    revalidated: bool
    revalidation_action: Optional[str]
    replacement_decision_id: Optional[str]
    execution_decision: Optional[str]
    audit_id: Optional[str]


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionFreshnessHistoryLink:
    """One old -> new decision replacement, taken from a freshness audit
    record's own replacement_decision_id. replacement_found is False when
    the decision store holds no decision under new_decision_id -- the link
    is still reported (the audit says it happened), never dropped or
    invented around."""

    old_decision_id: str
    new_decision_id: str
    audit_id: str
    linked_at: datetime
    replacement_found: bool


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionFreshnessHistory:
    """LLMAgentTaskRecoveryExecutionDecisionFreshnessHistoryService.
    get_history()'s read-only, chronological view of freshness-driven
    decision replacement for one task.

    original_decision_id is the task's earliest persisted decision (or, if
    the store holds none, the earliest audited one); current_decision_id
    is where the old -> new replacement chain starting there ends. gaps
    names every place the recorded chain is missing or interrupted --
    complete is True only when there are none.
    """

    task_id: str
    events: tuple
    links: tuple
    original_decision_id: Optional[str]
    current_decision_id: Optional[str]
    fresh_reuse_count: int
    revalidation_count: int
    replacement_count: int
    failed_revalidation_count: int
    gaps: tuple
    complete: bool
    generated_at: datetime


CHAIN_VALID = "valid"
CHAIN_INVALID = "invalid"
CHAIN_STATUSES = frozenset({CHAIN_VALID, CHAIN_INVALID})


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionFreshnessChainValidationResult:
    """LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService.
    validate()'s read-only verdict on whether task_id's freshness-driven
    replacement chain is internally consistent.

    chain is the decision_ids from the original decision to the chain's
    terminal point, as far as it could be followed. latest_decision_id is
    that terminal decision only when status is CHAIN_VALID -- fail closed:
    None whenever the current chain cannot be established.
    """

    task_id: str
    status: str
    issues: tuple
    chain: tuple
    latest_decision_id: Optional[str]
    validated_at: datetime

    @property
    def valid(self) -> bool:
        return self.status == CHAIN_VALID

    @property
    def invalid(self) -> bool:
        return self.status != CHAIN_VALID


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionFreshnessChainIndex:
    """Derived, non-authoritative chain metadata for one task, written only
    by LLMAgentTaskRecoveryExecutionDecisionFreshnessChainRepairService.
    links are (old_decision_id, new_decision_id) pairs; current_decision_id
    is the validated chain terminal, or None when the chain could not be
    validated. Safe to rebuild at any time -- decisions and audit records
    remain the source of truth."""

    task_id: str
    links: tuple
    current_decision_id: Optional[str]
    updated_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionFreshnessChainRepairResult:
    """LLMAgentTaskRecoveryExecutionDecisionFreshnessChainRepairService.
    repair()'s outcome: what was repaired, what could not be, and the
    chain validation results before and after."""

    task_id: str
    repaired: tuple
    unresolved: tuple
    initial_validation: "AgentTaskRecoveryExecutionDecisionFreshnessChainValidationResult"
    final_validation: "AgentTaskRecoveryExecutionDecisionFreshnessChainValidationResult"
    repaired_at: datetime

    @property
    def valid(self) -> bool:
        return self.final_validation.valid


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationResult:
    """LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService.
    reconcile()'s outcome. previous_current_decision_id is the chain
    index's current pointer before reconciling; authoritative_latest_decision_id
    is the validated chain's terminal decision (None when the chain is
    invalid -- fail closed). transition is the existing decision-state
    transition analysis for a pointer move, when one happened."""

    task_id: str
    previous_current_decision_id: Optional[str]
    authoritative_latest_decision_id: Optional[str]
    current_decision_id: Optional[str]
    current_decision_state: Optional[str]
    changes: tuple
    transition: Optional[object]
    unresolved: tuple
    final_chain_valid: bool
    reconciled_at: datetime
    # The subset of unresolved that are conflicting current pointers.
    conflicts: tuple = ()

    @property
    def changed(self) -> bool:
        return bool(self.changes)


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditRecord:
    """LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditService.
    record()'s durable, append-only capture of one freshness-chain
    reconciliation -- the same dual-index, append-only shape as
    AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord. Every field is
    copied verbatim from the reconciliation result; reconciled_at is the
    reconciliation's own timestamp, recorded_at when it was audited."""

    task_id: str
    previous_current_decision_id: Optional[str]
    authoritative_decision_id: Optional[str]
    current_decision_id: Optional[str]
    changed: bool
    changes: tuple
    conflicts: tuple
    chain_valid: bool
    unresolved: tuple
    reconciled_at: datetime
    recorded_at: datetime
    audit_id: str = field(default_factory=lambda: str(uuid4()))


RECONCILIATION_RESULT_SCHEMA_VERSION = 1
RECONCILIATION_COMPLETED = "completed"
RECONCILIATION_UNRESOLVED = "unresolved"
RECONCILIATION_STATUSES = frozenset({RECONCILIATION_COMPLETED, RECONCILIATION_UNRESOLVED})


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRecord:
    """LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultService.
    record()'s persisted, immutable outcome of one freshness-chain
    reconciliation. status is RECONCILIATION_COMPLETED only when the chain
    was valid and nothing was left unresolved or conflicting -- otherwise
    RECONCILIATION_UNRESOLVED, so a later run can tell a finished
    reconciliation from one still needing attention. Every other field is
    copied verbatim from the reconciliation result; schema_version is
    RECONCILIATION_RESULT_SCHEMA_VERSION at the time of recording."""

    task_id: str
    status: str
    previous_current_decision_id: Optional[str]
    authoritative_decision_id: Optional[str]
    current_decision_id: Optional[str]
    changed: bool
    changes: tuple
    conflicts: tuple
    unresolved: tuple
    chain_valid: bool
    reconciled_at: datetime
    recorded_at: datetime
    schema_version: int = RECONCILIATION_RESULT_SCHEMA_VERSION
    result_id: str = field(default_factory=lambda: str(uuid4()))
