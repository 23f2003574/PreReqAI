from datetime import datetime, timezone

from backend.agent_policy_engine import ALLOW

from .evaluation import LLMAgentTaskRecoveryGuardEvaluationService
from .models import APPROVED, REVOKED, AgentTaskRecoveryPreflightAuthorizationValidation
from .preflight_approval import LLMAgentTaskRecoveryPreflightApprovalService
from .preflight_authorization import LLMAgentTaskRecoveryPreflightAuthorizationService
from .preflight_freshness import LLMAgentTaskRecoveryPreflightFreshnessService
from .preflight_invalidation import LLMAgentTaskRecoveryPreflightInvalidationService
from .preflight_store import LLMAgentTaskRecoveryPreflightStore


class InvalidAgentTaskRecoveryPreflightAuthorizationValidationError(ValueError):
    """Raised when validate()/is_valid() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightAuthorizationValidationService:
    """A dedicated, read-only validation layer confirming a Commit #9
    execution authorization is STILL usable at the exact moment it would
    be consumed -- never a second validation/policy framework (Rule: "Do
    not create duplicate validation or policy infrastructure"): validate()
    only ever reads through Commit #9's own authorization service, Commit
    #4's own preflight store, Commit #6's own invalidation service (both
    its write-side invalidate_if_stale() elsewhere in this package, and
    its pure-read get_invalidation() here), Commit #5's own freshness
    check, Commit #8's own approval service, and Commit #2's own guard
    evaluation service -- exactly the same checks the rest of this
    package's own pipeline already performs, never re-derived a second
    way.

    Read-only, by construction (Rule: "Read-only; validation must not
    execute recovery or mutate task state"): unlike Commit #8's own
    `_verify_approvable()`/Commit #9's own `_verify_current_and_valid()`
    (which legitimately call Commit #6's own invalidate_if_stale() as
    part of a larger WRITE operation), this service calls ONLY read
    methods throughout -- get_invalidation() instead of
    invalidate_if_stale(), and no call anywhere to authorize()/approve()/
    reject()/revoke()/execute(). Calling validate() twice in a row can
    never itself change what the second call observes.

    Distinguishes every named failure case explicitly (Rule: "Clearly
    distinguish missing, revoked, stale, invalidated, superseded, and
    policy-blocked cases") -- collected, not stopped at the first: an
    authorization can simultaneously be, say, both stale AND no longer
    policy-permitted, and both are reported, the same "report every
    reason, never only the first" discipline this whole project already
    establishes elsewhere.

        missing        -> no authorization_id on record for task_id, or
                           its own referenced preflight_id no longer
                           exists in Commit #4's own history at all
        revoked        -> Commit #9's own authorization.status is REVOKED
        superseded     -> the referenced preflight_id is no longer
                           task_id's own CURRENT stored preflight (Commit
                           #4's own get())
        invalidated    -> Commit #6's own get_invalidation() finds an
                           existing (explicit or previously-detected-
                           stale) invalidation record for it
        stale          -> Commit #5's own freshness check (called
                           directly here, read-only) reports is_fresh
                           False -- also covers "authorization ...
                           inconsistent with the current recovery plan",
                           since that is exactly what Commit #5's own
                           plan_identity comparison already detects,
                           reused rather than re-implemented a second way
        lapsed approval -> Commit #8's own approval record for this
                           exact preflight_id is missing or no longer
                           APPROVED
        policy-blocked  -> a FRESH Commit #2 evaluate() call against the
                           preflight's own embedded plan no longer
                           returns ALLOW right now

    A missing authorization_id (or one that names no known preflight at
    all) short-circuits with just that one reason -- there is nothing
    else meaningful to check once the subject itself does not exist.
    Every other case runs ALL of the remaining checks and reports every
    one that applies.

    is_valid() is the same check, reduced to a bare bool, for a caller
    that only needs a gate -- never a second, cheaper-but-different
    implementation of the same question.
    """

    def __init__(
        self,
        authorization_service: LLMAgentTaskRecoveryPreflightAuthorizationService = None,
        preflight_store: LLMAgentTaskRecoveryPreflightStore = None,
        invalidation_service: LLMAgentTaskRecoveryPreflightInvalidationService = None,
        freshness_service: LLMAgentTaskRecoveryPreflightFreshnessService = None,
        approval_service: LLMAgentTaskRecoveryPreflightApprovalService = None,
        evaluation_service: LLMAgentTaskRecoveryGuardEvaluationService = None,
    ):
        self._preflight_store = (
            preflight_store if preflight_store is not None else LLMAgentTaskRecoveryPreflightStore()
        )
        self._invalidation_service = (
            invalidation_service
            if invalidation_service is not None
            else LLMAgentTaskRecoveryPreflightInvalidationService(preflight_store=self._preflight_store)
        )
        self._freshness_service = (
            freshness_service
            if freshness_service is not None
            else LLMAgentTaskRecoveryPreflightFreshnessService(preflight_store=self._preflight_store)
        )
        self._approval_service = (
            approval_service
            if approval_service is not None
            else LLMAgentTaskRecoveryPreflightApprovalService(
                preflight_store=self._preflight_store, invalidation_service=self._invalidation_service
            )
        )
        self._evaluation_service = (
            evaluation_service if evaluation_service is not None else LLMAgentTaskRecoveryGuardEvaluationService()
        )
        self._authorization_service = (
            authorization_service
            if authorization_service is not None
            else LLMAgentTaskRecoveryPreflightAuthorizationService(
                preflight_store=self._preflight_store,
                approval_service=self._approval_service,
                invalidation_service=self._invalidation_service,
                evaluation_service=self._evaluation_service,
            )
        )

    def validate(self, task_id: str, authorization_id: str) -> AgentTaskRecoveryPreflightAuthorizationValidation:
        """Check whether task_id's exact authorization_id is still valid
        to consume right now.

        Raises:
            InvalidAgentTaskRecoveryPreflightAuthorizationValidationError:
                If task_id or authorization_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(authorization_id, "authorization_id")
        now = datetime.now(timezone.utc)

        authorization = self._authorization_service.get(task_id, authorization_id)
        if authorization is None:
            return AgentTaskRecoveryPreflightAuthorizationValidation(
                valid=False, task_id=task_id, authorization_id=authorization_id, preflight_id=None,
                blocking_reasons=("no authorization is recorded for this task_id/authorization_id",),
                warnings=(), validated_at=now,
            )

        preflight_id = authorization.preflight_id
        blocking_reasons: list = []
        warnings: list = []

        if authorization.status == REVOKED:
            blocking_reasons.append(f"authorization has been revoked: {authorization.revocation_reason}")

        preflight = next(
            (record for record in self._preflight_store.history(task_id) if record.preflight_id == preflight_id),
            None,
        )
        if preflight is None:
            blocking_reasons.append("the referenced preflight no longer exists")
            return AgentTaskRecoveryPreflightAuthorizationValidation(
                valid=False, task_id=task_id, authorization_id=authorization_id, preflight_id=preflight_id,
                blocking_reasons=tuple(blocking_reasons), warnings=(), validated_at=now,
            )

        current = self._preflight_store.get(task_id)
        if current is None or current.preflight_id != preflight_id:
            blocking_reasons.append("the referenced preflight has been superseded by a newer preflight")

        existing_invalidation = self._invalidation_service.get_invalidation(preflight_id)
        if existing_invalidation is not None:
            blocking_reasons.append(f"the referenced preflight has been invalidated: {existing_invalidation.reason}")

        freshness = self._freshness_service.check(task_id, preflight=preflight)
        if not freshness.is_fresh:
            blocking_reasons.extend(f"stale: {reason}" for reason in freshness.stale_reasons)

        approval = self._approval_service.get(task_id, preflight_id)
        if approval is None or approval.status != APPROVED:
            blocking_reasons.append("the required approval no longer applies to this exact preflight")

        if preflight.plan is None:
            blocking_reasons.append("the referenced preflight has no recovery plan")
        else:
            evaluation = self._evaluation_service.evaluate(task_id, preflight.plan)
            if evaluation.decision != ALLOW:
                blocking_reasons.append(
                    f"current recovery guard/policy evaluation is {evaluation.decision!r}, not {ALLOW!r}: "
                    f"{evaluation.reason}"
                )
            warnings.extend(evaluation.warnings)

        return AgentTaskRecoveryPreflightAuthorizationValidation(
            valid=not blocking_reasons,
            task_id=task_id,
            authorization_id=authorization_id,
            preflight_id=preflight_id,
            blocking_reasons=tuple(blocking_reasons),
            warnings=tuple(warnings),
            validated_at=now,
        )

    def is_valid(self, task_id: str, authorization_id: str) -> bool:
        """The same check as validate(), reduced to a bare bool."""
        return self.validate(task_id, authorization_id).valid

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightAuthorizationValidationError(
                f"{field_name} is required and must be a non-empty string"
            )
