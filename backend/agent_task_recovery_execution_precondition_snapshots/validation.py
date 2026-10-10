from datetime import datetime, timezone

from backend.agent_task_recovery_guardrails import (
    LLMAgentTaskRecoveryGuardService,
    LLMAgentTaskRecoveryPreflightAuthorizationValidationService,
)

from .models import AgentTaskRecoveryExecutionPreconditionValidationResult
from .service import LLMAgentTaskRecoveryExecutionPreconditionSnapshotService


class InvalidAgentTaskRecoveryExecutionPreconditionValidationError(ValueError):
    """Raised when validate()/is_valid() is given invalid arguments, or
    snapshot_id names no recorded Commit #1 snapshot for task_id."""


class LLMAgentTaskRecoveryExecutionPreconditionValidationService:
    """Validates that a Commit #1
    AgentTaskRecoveryExecutionPreconditionSnapshot's captured baseline
    still holds immediately before that authorization's bound recovery
    plan would be handed to backend.agent_task_event_analytics.
    LLMAgentTaskFailureRecoveryService.execute_plan() -- never a second
    policy engine, dependency resolver, or authorization framework
    (Rule: "Reuse existing validators; don't recreate policy/dependency
    logic"): every blocking fact is read straight from two already-
    existing, already-comprehensive validators:

      backend.agent_task_recovery_guardrails.
        LLMAgentTaskRecoveryPreflightAuthorizationValidationService.
        validate() -- authorization validity/binding to the same
        recovery (revoked/superseded/invalidated/stale/lapsed-approval/
        policy-blocked; "preflight/dependency evidence is still valid"
        is exactly its own freshness+approval+policy checks)
      backend.agent_task_recovery_guardrails.LLMAgentTaskRecoveryGuardService.
        validate() -- task eligibility, plan freshness ("authorized
        recovery action/plan is unchanged"), action/policy permission,
        retry/budget constraints, dependency readiness, and conflicting
        active recovery

    Read-only (Rule): validate()/is_valid() only ever call other
    services' own read methods (get()/compare()/validate()) -- nothing
    here calls authorize()/consume()/execute()/execute_plan() or any
    other write path anywhere else in this repository.

    Fails closed on material state changes (Rule): valid is exactly `not
    blocking_reasons`, and blocking_reasons is populated only from the
    two validators above (plus the one case neither of them can express:
    the snapshot itself captured no recovery_plan at all, which alone
    makes execution unvalidatable). Clearly distinguishes harmless from
    execution-blocking changes (Rule): Commit #1's own, purely
    informational compare() diff is carried through unchanged as `diff`
    -- it can report `changed=True` for a harmless improvement (a
    dependency resolved, retry eligibility improved) while `valid` stays
    True, since valid/blocking_reasons never read diff's own booleans at
    all, only the two validators' own verdicts.

    Integrate this by calling validate() (or is_valid()) with the exact
    snapshot_id Commit #1's capture() produced, immediately before
    handing that authorization's own bound recovery plan to
    LLMAgentTaskFailureRecoveryService.execute_plan() -- not by importing
    into that module directly: backend.agent_task_event_analytics is
    upstream of backend.agent_task_recovery_guardrails (and of this
    package), so importing either back into it would be circular.
    """

    def __init__(
        self,
        snapshot_service: LLMAgentTaskRecoveryExecutionPreconditionSnapshotService = None,
        guard_service: LLMAgentTaskRecoveryGuardService = None,
        authorization_validation_service: LLMAgentTaskRecoveryPreflightAuthorizationValidationService = None,
    ):
        """
        Args:
            snapshot_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionSnapshotService;
                pass the real instance holding the snapshot capture()
                actually produced for validate() to ever find it.
            guard_service: Defaults to a fresh
                LLMAgentTaskRecoveryGuardService; pass the real instance
                wired with live readiness/retry-eligibility/retry-
                scheduler/dead-letter/reservation collaborators for its
                own checks to reflect real state.
            authorization_validation_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightAuthorizationValidationService;
                pass the real instance wired to the same authorization/
                preflight stores the snapshot's own authorization_id was
                recorded through.
        """
        self._snapshot_service = (
            snapshot_service if snapshot_service is not None else LLMAgentTaskRecoveryExecutionPreconditionSnapshotService()
        )
        self._guard_service = guard_service if guard_service is not None else LLMAgentTaskRecoveryGuardService()
        self._authorization_validation_service = (
            authorization_validation_service
            if authorization_validation_service is not None
            else LLMAgentTaskRecoveryPreflightAuthorizationValidationService()
        )

    def validate(self, task_id: str, snapshot_id: str) -> AgentTaskRecoveryExecutionPreconditionValidationResult:
        """Check whether task_id's exact Commit #1 snapshot_id's captured
        baseline still holds right now.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionValidationError:
                If task_id/snapshot_id is not a non-empty string, or
                snapshot_id names no recorded snapshot for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")

        snapshot = self._snapshot_service.get(task_id, snapshot_id)
        if snapshot is None:
            raise InvalidAgentTaskRecoveryExecutionPreconditionValidationError(
                f"no snapshot {snapshot_id!r} is recorded for task_id {task_id!r}"
            )

        diff = self._snapshot_service.compare(task_id, snapshot_id)
        authorization_validation = self._authorization_validation_service.validate(task_id, snapshot.authorization_id)

        blocking_reasons = list(authorization_validation.blocking_reasons)
        warnings = list(authorization_validation.warnings)

        guard_result = None
        if snapshot.recovery_plan is None:
            blocking_reasons.append("no recovery plan was captured in this snapshot to validate for execution")
        else:
            guard_result = self._guard_service.validate(task_id, snapshot.recovery_plan)
            blocking_reasons.extend(guard_result.violations)
            warnings.extend(guard_result.warnings)

        return AgentTaskRecoveryExecutionPreconditionValidationResult(
            task_id=task_id,
            snapshot_id=snapshot_id,
            authorization_id=snapshot.authorization_id,
            preflight_id=snapshot.preflight_id,
            valid=not blocking_reasons,
            blocking_reasons=tuple(blocking_reasons),
            warnings=tuple(warnings),
            diff=diff,
            authorization_validation=authorization_validation,
            guard_result=guard_result,
            validated_at=self._now(),
        )

    def is_valid(self, task_id: str, snapshot_id: str) -> bool:
        """The same check as validate(), reduced to a bare bool."""
        return self.validate(task_id, snapshot_id).valid

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionPreconditionValidationError(
                f"{field_name} is required and must be a non-empty string"
            )
