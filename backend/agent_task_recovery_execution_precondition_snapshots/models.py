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
