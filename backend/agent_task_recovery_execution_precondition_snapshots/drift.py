from datetime import datetime, timezone

from backend.agent_task_lifecycle import CANCELLED, FAILED, TERMINAL_STATES
from backend.agent_task_recovery_guardrails import ACTIVE, AUTHORIZATION_STATUSES

from .models import (
    _DRIFT_SEVERITY,
    DRIFT_EXECUTION_BLOCKED,
    DRIFT_NON_BLOCKING,
    DRIFT_NONE,
    DRIFT_REQUIRES_REVALIDATION,
    AgentTaskRecoveryExecutionPreconditionDriftItem,
    AgentTaskRecoveryExecutionPreconditionDriftResult,
)
from .validation import LLMAgentTaskRecoveryExecutionPreconditionValidationService

# Terminal-and-failing states recovery is meaningfully applicable to (the
# same set backend.agent_task_recovery_guardrails.LLMAgentTaskRecoveryGuardService
# ._check_task_eligibility already treats as eligible) -- reused verbatim,
# never re-derived.
_TERMINAL_ELIGIBLE_STATES = frozenset({FAILED, CANCELLED})


class InvalidAgentTaskRecoveryExecutionPreconditionDriftError(ValueError):
    """Raised when classify() is given invalid arguments, or snapshot_id
    names no recorded Commit #1 snapshot for task_id."""


class LLMAgentTaskRecoveryExecutionPreconditionDriftService:
    """Classifies the differences Commit #2's own validate() already found
    between a Commit #1 snapshot's captured baseline and task_id's current
    state -- never a second validation engine (Rule: "Do not create
    another validation engine"): classify() calls
    LLMAgentTaskRecoveryExecutionPreconditionValidationService.validate()
    exactly once and derives every field below purely from its own
    `diff.changes`/`blocking_reasons` (Rule: "Base classification only on
    the existing validation diff"), never re-checking policy, dependency,
    retry-budget, or authorization state a second, independent way.
    previous_value/current_value on every item are exactly Commit #2's own
    diff.changes entries, never re-derived or re-fetched a second way.

    Maps each Commit #1 snapshot field to the same named recovery concern
    backend.agent_task_recovery_guardrails.LLMAgentTaskRecoveryGuardService.
    validate() already checks under (Rule: "Reuse existing policy/risk/
    severity semantics where available"): authorization_status ->
    "authorization", task_state -> "task_eligibility", retry_eligibility ->
    "retry_budget", readiness -> "dependency_and_policy_readiness" (Commit
    #1's own readiness field already bundles guard's own "dependencies"
    and "policy" named checks into one read).

    execution_may_continue is always exactly `validation.valid` (Rule:
    "Never approve or execute recovery itself"): this class only explains,
    per field, why Commit #2's fresh re-validation reached the verdict it
    did -- it never overrides that verdict, upgrades a blocked state to
    non-blocking, or downgrades a non-blocking state to blocked.

    Fails closed on anything it cannot safely classify (Rule): a field
    whose current value can no longer even be read (e.g. a collaborator
    that was wired at capture time is no longer wired at compare time) is
    REQUIRES_REVALIDATION, never silently treated as NON_BLOCKING; a
    blocking_reasons entry the validator reported that no tracked field's
    own change explains produces a synthetic, unclassified
    EXECUTION_BLOCKED item rather than being silently dropped.
    """

    def __init__(self, validation_service: LLMAgentTaskRecoveryExecutionPreconditionValidationService = None):
        """
        Args:
            validation_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionValidationService;
                pass the real instance wired to the same snapshot/guard/
                authorization-validation stack the snapshot was captured
                and validated through.
        """
        self._validation_service = (
            validation_service
            if validation_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionValidationService()
        )

    def classify(self, task_id: str, snapshot_id: str) -> AgentTaskRecoveryExecutionPreconditionDriftResult:
        """Classify task_id's exact Commit #1 snapshot_id's observed drift.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionDriftError: If
                task_id/snapshot_id is not a non-empty string, or
                snapshot_id names no recorded snapshot for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")

        try:
            validation = self._validation_service.validate(task_id, snapshot_id)
        except Exception as error:
            raise InvalidAgentTaskRecoveryExecutionPreconditionDriftError(str(error)) from error

        changes_by_field = {change.field: change for change in validation.diff.changes}

        items = [
            self._classify_authorization_status(changes_by_field.get("authorization_status")),
            self._classify_task_state(changes_by_field.get("task_state")),
            self._classify_retry_eligibility(changes_by_field.get("retry_eligibility")),
            self._classify_readiness(changes_by_field.get("readiness")),
        ]
        items = [item for item in items if item is not None]

        explained = any(item.category == DRIFT_EXECUTION_BLOCKED for item in items)
        if not validation.valid and not explained:
            items.append(
                AgentTaskRecoveryExecutionPreconditionDriftItem(
                    field=None,
                    concern="unclassified",
                    category=DRIFT_EXECUTION_BLOCKED,
                    previous_value=None,
                    current_value=tuple(validation.blocking_reasons),
                    reason=(
                        "execution is blocked for a reason not reflected in any tracked precondition field: "
                        + "; ".join(validation.blocking_reasons)
                    ),
                    execution_may_continue=False,
                )
            )

        category = DRIFT_NONE
        for item in items:
            if _DRIFT_SEVERITY[item.category] > _DRIFT_SEVERITY[category]:
                category = item.category

        return AgentTaskRecoveryExecutionPreconditionDriftResult(
            task_id=task_id,
            snapshot_id=snapshot_id,
            authorization_id=validation.authorization_id,
            preflight_id=validation.preflight_id,
            category=category,
            execution_may_continue=validation.valid,
            items=tuple(items),
            blocking_reasons=validation.blocking_reasons,
            warnings=validation.warnings,
            validation=validation,
            classified_at=self._now(),
        )

    @staticmethod
    def _classify_authorization_status(change):
        if change is None:
            return None
        concern = "authorization"
        current_status = change.current_value
        if current_status not in AUTHORIZATION_STATUSES:
            return AgentTaskRecoveryExecutionPreconditionDriftItem(
                field=change.field, concern=concern, category=DRIFT_EXECUTION_BLOCKED,
                previous_value=change.previous_value, current_value=current_status,
                reason="authorization status can no longer be determined", execution_may_continue=False,
            )
        if current_status != ACTIVE:
            return AgentTaskRecoveryExecutionPreconditionDriftItem(
                field=change.field, concern=concern, category=DRIFT_EXECUTION_BLOCKED,
                previous_value=change.previous_value, current_value=current_status,
                reason=f"authorization is no longer active (status={current_status!r})",
                execution_may_continue=False,
            )
        return AgentTaskRecoveryExecutionPreconditionDriftItem(
            field=change.field, concern=concern, category=DRIFT_REQUIRES_REVALIDATION,
            previous_value=change.previous_value, current_value=current_status,
            reason="authorization status changed since capture even though it is currently active",
            execution_may_continue=True,
        )

    @staticmethod
    def _classify_task_state(change):
        if change is None:
            return None
        concern = "task_eligibility"
        current_state = change.current_value
        if current_state is None:
            return AgentTaskRecoveryExecutionPreconditionDriftItem(
                field=change.field, concern=concern, category=DRIFT_EXECUTION_BLOCKED,
                previous_value=change.previous_value, current_value=None,
                reason="task lifecycle state can no longer be determined", execution_may_continue=False,
            )
        if current_state in TERMINAL_STATES and current_state not in _TERMINAL_ELIGIBLE_STATES:
            return AgentTaskRecoveryExecutionPreconditionDriftItem(
                field=change.field, concern=concern, category=DRIFT_EXECUTION_BLOCKED,
                previous_value=change.previous_value, current_value=current_state,
                reason=f"task has reached terminal state {current_state!r}; recovery no longer applies",
                execution_may_continue=False,
            )
        return AgentTaskRecoveryExecutionPreconditionDriftItem(
            field=change.field, concern=concern, category=DRIFT_REQUIRES_REVALIDATION,
            previous_value=change.previous_value, current_value=current_state,
            reason=f"task lifecycle state changed to {current_state!r} since capture",
            execution_may_continue=True,
        )

    @staticmethod
    def _classify_retry_eligibility(change):
        if change is None:
            return None
        concern = "retry_budget"
        current = change.current_value
        if current is None:
            return AgentTaskRecoveryExecutionPreconditionDriftItem(
                field=change.field, concern=concern, category=DRIFT_REQUIRES_REVALIDATION,
                previous_value=change.previous_value, current_value=None,
                reason="retry eligibility can no longer be read; cannot be safely compared",
                execution_may_continue=True,
            )
        if not current.eligible:
            return AgentTaskRecoveryExecutionPreconditionDriftItem(
                field=change.field, concern=concern, category=DRIFT_EXECUTION_BLOCKED,
                previous_value=change.previous_value, current_value=current,
                reason=f"retry is no longer eligible: {current.reason}", execution_may_continue=False,
            )
        return AgentTaskRecoveryExecutionPreconditionDriftItem(
            field=change.field, concern=concern, category=DRIFT_NON_BLOCKING,
            previous_value=change.previous_value, current_value=current,
            reason="retry eligibility changed since capture but remains eligible", execution_may_continue=True,
        )

    @staticmethod
    def _classify_readiness(change):
        if change is None:
            return None
        concern = "dependency_and_policy_readiness"
        current = change.current_value
        if current is None:
            return AgentTaskRecoveryExecutionPreconditionDriftItem(
                field=change.field, concern=concern, category=DRIFT_REQUIRES_REVALIDATION,
                previous_value=change.previous_value, current_value=None,
                reason="readiness can no longer be read; cannot be safely compared", execution_may_continue=True,
            )
        if not current.ready:
            return AgentTaskRecoveryExecutionPreconditionDriftItem(
                field=change.field, concern=concern, category=DRIFT_EXECUTION_BLOCKED,
                previous_value=change.previous_value, current_value=current,
                reason="readiness is no longer satisfied: " + "; ".join(current.blocking_reasons),
                execution_may_continue=False,
            )
        return AgentTaskRecoveryExecutionPreconditionDriftItem(
            field=change.field, concern=concern, category=DRIFT_NON_BLOCKING,
            previous_value=change.previous_value, current_value=current,
            reason="readiness changed since capture but remains satisfied", execution_may_continue=True,
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionPreconditionDriftError(
                f"{field_name} is required and must be a non-empty string"
            )
