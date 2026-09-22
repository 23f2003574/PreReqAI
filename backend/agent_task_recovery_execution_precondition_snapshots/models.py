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
