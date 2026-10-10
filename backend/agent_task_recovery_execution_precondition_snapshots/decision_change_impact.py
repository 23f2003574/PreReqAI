from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .decision_transition import LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService
from .models import (
    CHANGE_IMPACT_ENABLED,
    CHANGE_IMPACT_RELAXED,
    CHANGE_IMPACT_RESTRICTED,
    CHANGE_IMPACT_STILL_BLOCKED,
    CHANGE_IMPACT_UNCHANGED,
    CHANGE_IMPACT_UNKNOWN,
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    RESOLUTION_RESOLVED,
    AgentTaskRecoveryExecutionDecisionChangeImpactResult,
)

_SEVERITY = {EXECUTION_DECISION_ALLOW: 0, EXECUTION_DECISION_REVIEW: 1, EXECUTION_DECISION_BLOCK: 2}

# (area, snapshot field) pairs compared between the two decisions' own
# persisted precondition snapshots, in reporting order.
_SNAPSHOT_AREAS = (
    ("authorization", ("authorization_id", "authorization_status", "approval_id")),
    ("preflight", ("preflight_id",)),
    ("task_state", ("task_state",)),
    ("recovery_plan", ("recovery_plan",)),
    ("retry_budget", ("retry_eligibility",)),
    ("readiness", ("readiness",)),
)


class InvalidAgentTaskRecoveryExecutionDecisionChangeImpactError(ValueError):
    """Raised when analyze() is given invalid arguments."""


class LLMAgentTaskRecoveryExecutionDecisionChangeImpactService:
    """Determines what existing task/recovery state is affected when the
    authoritative execution decision changes -- an analysis layer over
    persisted evidence, not another decision-management layer: it reads
    the two persisted decisions (decision store), their own persisted
    precondition snapshots (snapshot service get(), never capture()/
    compare() against live state), the existing decision transition
    analysis, and optionally the supersession resolution. It never reruns
    the decision engine, authorizes, or executes anything.

    Only evidence-backed impact is reported: an area is "changed" only
    when both persisted snapshots exist and differ in it; a snapshot that
    cannot be read is listed in missing_evidence and forces revalidation
    instead of being guessed about.
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        snapshot_service=None,
        transition_service: LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService = None,
        supersession_resolution_service=None,
    ):
        """snapshot_service is the existing
        LLMAgentTaskRecoveryExecutionPreconditionSnapshotService (only its
        get() is used); without it, snapshot-backed areas are reported as
        missing evidence. supersession_resolution_service, when given,
        checks that current_decision_id is the authoritative terminal."""
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        self._snapshot_service = snapshot_service
        self._transition_service = (
            transition_service if transition_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService(store=self._decision_store)
        )
        self._resolution_service = supersession_resolution_service

    def analyze(
        self, task_id: str, previous_decision_id: str, current_decision_id: str
    ) -> AgentTaskRecoveryExecutionDecisionChangeImpactResult:
        """Analyze the impact of moving from previous_decision_id to
        current_decision_id for task_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionChangeImpactError:
                If any argument is not a non-empty string
        """
        for value, name in (
            (task_id, "task_id"), (previous_decision_id, "previous_decision_id"),
            (current_decision_id, "current_decision_id"),
        ):
            if not value or not isinstance(value, str):
                raise InvalidAgentTaskRecoveryExecutionDecisionChangeImpactError(
                    f"{name} is required and must be a non-empty string"
                )

        previous = self._owned(task_id, previous_decision_id)
        current = self._owned(task_id, current_decision_id)
        missing = []
        for label, decision_id, decision in (
            ("previous", previous_decision_id, previous), ("current", current_decision_id, current),
        ):
            if decision is None:
                missing.append(f"{label} decision {decision_id} is not recorded for task {task_id}")
        if missing:
            return AgentTaskRecoveryExecutionDecisionChangeImpactResult(
                task_id=task_id, previous_decision_id=previous_decision_id,
                current_decision_id=current_decision_id,
                previous_decision=previous.decision if previous is not None else None,
                current_decision=current.decision if current is not None else None,
                changed_areas=(), stale_artifacts=(),
                blocking_conditions=("decision references are missing; execution impact cannot be established",),
                requires_revalidation=True, execution_impact=CHANGE_IMPACT_UNKNOWN, transition=None,
                missing_evidence=tuple(missing),
            )

        changed, stale = [], []
        transition = None
        if previous_decision_id != current_decision_id:
            try:
                transition = self._transition_service.analyze(task_id, current_decision_id, previous_decision_id)
            except ValueError as error:
                missing.append(f"transition could not be analyzed: {error}")
        if previous.decision != current.decision:
            changed.append("decision_state")
            stale.append(f"execution eligibility derived from {previous.decision} decision {previous_decision_id}")
        if previous.blocking_conditions != current.blocking_conditions:
            changed.append("blocking_conditions")

        if previous.snapshot_id != current.snapshot_id:
            changed.append("precondition_snapshot")
            stale.append(f"precondition snapshot {previous.snapshot_id}")
            before = self._snapshot(task_id, previous.snapshot_id, missing)
            after = self._snapshot(task_id, current.snapshot_id, missing)
            if before is not None and after is not None:
                for area, fields in _SNAPSHOT_AREAS:
                    if any(getattr(before, f) != getattr(after, f) for f in fields):
                        changed.append(area)
                        if area == "authorization":
                            stale.append(f"authorization {before.authorization_id}")
                        elif area == "recovery_plan":
                            stale.append(f"recovery plan captured in snapshot {previous.snapshot_id}")
                        elif area == "retry_budget":
                            stale.append(f"retry/budget eligibility captured in snapshot {previous.snapshot_id}")

        blocking = list(current.blocking_conditions)
        if current.decision != EXECUTION_DECISION_ALLOW:
            blocking.append(f"current decision {current_decision_id} is {current.decision}")
        if self._resolution_service is not None:
            resolution = self._resolution_service.resolve(task_id)
            if resolution.resolution_state != RESOLUTION_RESOLVED:
                blocking.append(f"the decision lineage does not resolve ({resolution.resolution_state})")
            elif resolution.terminal_decision_id != current_decision_id:
                blocking.append(
                    f"decision {current_decision_id} is not the authoritative terminal "
                    f"{resolution.terminal_decision_id}"
                )

        impact = self._impact(previous.decision, current.decision, changed)
        requires_revalidation = bool(
            missing or current.decision != EXECUTION_DECISION_ALLOW
            or {"precondition_snapshot", "authorization", "recovery_plan", "retry_budget"} & set(changed)
            or len(blocking) > len(current.blocking_conditions)
        )
        return AgentTaskRecoveryExecutionDecisionChangeImpactResult(
            task_id=task_id, previous_decision_id=previous_decision_id, current_decision_id=current_decision_id,
            previous_decision=previous.decision, current_decision=current.decision, changed_areas=tuple(changed),
            stale_artifacts=tuple(stale), blocking_conditions=tuple(blocking),
            requires_revalidation=requires_revalidation, execution_impact=impact, transition=transition,
            missing_evidence=tuple(missing),
        )

    def _owned(self, task_id, decision_id):
        decision = self._decision_store.get(decision_id)
        return decision if decision is not None and decision.task_id == task_id else None

    def _snapshot(self, task_id, snapshot_id, missing):
        if self._snapshot_service is None:
            missing.append(f"precondition snapshot {snapshot_id} could not be read (no snapshot service)")
            return None
        snapshot = self._snapshot_service.get(task_id, snapshot_id)
        if snapshot is None:
            missing.append(f"precondition snapshot {snapshot_id} is not recorded for task {task_id}")
        return snapshot

    @staticmethod
    def _impact(before, after, changed):
        if before == after:
            if after != EXECUTION_DECISION_ALLOW:
                return CHANGE_IMPACT_STILL_BLOCKED
            return CHANGE_IMPACT_UNCHANGED
        if after == EXECUTION_DECISION_ALLOW:
            return CHANGE_IMPACT_ENABLED
        if _SEVERITY[after] > _SEVERITY[before]:
            return CHANGE_IMPACT_RESTRICTED
        return CHANGE_IMPACT_RELAXED
