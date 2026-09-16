from datetime import datetime, timezone

from backend.agent_task_recovery_guardrails import LLMAgentTaskRecoveryPreflightAuthorizationValidationService

from .models import CANCELLED, AgentTaskRecoveryScheduleValidation
from .service import LLMAgentTaskRecoveryPreflightSchedulingService


class InvalidAgentTaskRecoveryScheduleValidationError(ValueError):
    """Raised when validate()/is_executable() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightScheduleValidationService:
    """Confirms one Commit #1 schedule is STILL safe to execute right
    now -- never a second scheduler or validation framework (Rule): every
    check here reuses an existing read: Commit #1's own scheduling
    service (existence/task binding/cancelled/effective-invalidation --
    the latter itself already reusing Commit #10-of-agent_task_recovery_
    guardrails' own authorization validation internally) plus a direct
    call to that SAME validation service for the detailed, itemized
    reasons (superseded/invalidated/stale/lapsed-approval/policy-blocked)
    -- nothing here re-derives freshness, guard, or authorization logic a
    second way.

    Read-only (Rule): validate() never calls schedule()/cancel()/
    authorize()/consume() -- only get()/validate() reads throughout.

    The one genuinely new check here is the execution window itself
    (Rule: "schedule has actually reached its execution window") -- a
    schedule with execute_at in the future is not yet executable, a
    plain datetime comparison, never a second scheduling mechanism.

    Fails closed (Rule): a missing/cancelled/invalidated/not-yet-due
    schedule is reported invalid, never defaulted to valid.

    dependency_service, when supplied, is Commit #1(-of-the-dependency-
    gate-series)'s own backend.agent_task_recovery_schedule_dependencies.
    LLMAgentTaskRecoveryPreflightScheduleDependencyService -- deliberately
    accepted untyped/duck-typed here (mirrors this package's own
    dispatch.py accepting queue_service the same way) so this earlier
    package never has to import the later one and risk a circular
    import between them. Left None (the default), no dependency check
    ever runs and existing callers see no behavior change at all; when
    given, its own check(task_id, schedule_id).blockers are folded
    straight into blocking_reasons -- Rule: "Integrate the gate into
    the existing schedule validation/dispatch path so it actually
    affects dispatch eligibility," since dispatch.py's own dispatch()
    already refuses to hand off a schedule this validate() reports
    invalid.
    """

    def __init__(
        self,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        authorization_validation_service: LLMAgentTaskRecoveryPreflightAuthorizationValidationService = None,
        dependency_service=None,
    ):
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._authorization_validation_service = (
            authorization_validation_service
            if authorization_validation_service is not None
            else LLMAgentTaskRecoveryPreflightAuthorizationValidationService()
        )
        self._dependency_service = dependency_service

    def validate(self, task_id: str, schedule_id: str) -> AgentTaskRecoveryScheduleValidation:
        """Check whether task_id's exact schedule_id is still executable
        right now.

        Raises:
            InvalidAgentTaskRecoveryScheduleValidationError: If task_id
                or schedule_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        now = datetime.now(timezone.utc)

        schedule = self._scheduling_service.get(task_id, schedule_id)
        if schedule is None:
            return AgentTaskRecoveryScheduleValidation(
                valid=False, task_id=task_id, schedule_id=schedule_id, preflight_id=None,
                blocking_reasons=("no schedule is recorded for this task_id/schedule_id",),
                warnings=(), validated_at=now,
            )

        blocking_reasons: list = []
        warnings: list = []

        if schedule.status == CANCELLED:
            blocking_reasons.append("schedule has been cancelled")

        authorization_validation = self._authorization_validation_service.validate(
            task_id, schedule.authorization_id
        )
        if not authorization_validation.valid:
            blocking_reasons.extend(authorization_validation.blocking_reasons)
        warnings.extend(authorization_validation.warnings)

        if schedule.execute_at is not None and now < schedule.execute_at:
            blocking_reasons.append(
                f"execution window has not been reached yet (scheduled for {schedule.execute_at.isoformat()})"
            )

        if self._dependency_service is not None:
            dependency_result = self._dependency_service.check(task_id, schedule_id)
            blocking_reasons.extend(dependency_result.blockers)

        return AgentTaskRecoveryScheduleValidation(
            valid=not blocking_reasons,
            task_id=task_id,
            schedule_id=schedule_id,
            preflight_id=schedule.preflight_id,
            blocking_reasons=tuple(blocking_reasons),
            warnings=tuple(warnings),
            validated_at=now,
        )

    def is_executable(self, task_id: str, schedule_id: str) -> bool:
        """The same check as validate(), reduced to a bare bool."""
        return self.validate(task_id, schedule_id).valid

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleValidationError(
                f"{field_name} is required and must be a non-empty string"
            )
