from backend.agent_policy_engine import ALLOW

from .models import APPROVED, AgentTaskRecoveryOrchestrationResult
from .preflight_approval import LLMAgentTaskRecoveryPreflightApprovalService
from .preflight_authorization import LLMAgentTaskRecoveryPreflightAuthorizationService
from .preflight_authorization_consumption import LLMAgentTaskRecoveryPreflightAuthorizationConsumptionService
from .preflight_authorization_validation import LLMAgentTaskRecoveryPreflightAuthorizationValidationService
from .preflight_revalidation import LLMAgentTaskRecoveryPreflightRevalidationService


class InvalidAgentTaskRecoveryOrchestrationError(ValueError):
    """Raised when execute() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightOrchestrationService:
    """The single, thin entry point closing the whole day's own recovery-
    preflight lifecycle: current preflight -> approval -> authorization
    -> validation -> consumption -- never a second recovery engine or
    workflow/state-machine framework (Rule): every step here is exactly
    one existing service's own already-published method, called
    unchanged and in order:

        resolve/revalidate     Commit #7 revalidation_service.revalidate()
        require approved       Commit #8 approval_service.get()
        create/reuse auth      Commit #9 authorization_service.authorize()
        validate before use    Commit #10 validation_service.validate()
        consume                Commit #11 consumption_service.consume()
                                (itself auditing via Commit #12 when wired)

    No business logic is duplicated anywhere in this class -- it only
    ever reads a prior step's own result to decide whether to call the
    next one, and assembles their outputs into one combined report.

    Fails closed at every gate (Rule): the moment any step reports
    anything other than "go" (a non-ALLOW current decision, a missing/
    non-APPROVED approval, a validation failure, or an exception from
    authorize()/consume() itself), execute() stops immediately and
    returns executed=False with the specific blocking reason -- it never
    falls through to a later step on a failed one.

    Never bypasses any existing safeguard (Rule): authorize()/consume()
    are called completely unmodified, so every guard/policy/retry/budget/
    dependency check those services already themselves enforce (Commits
    #1/#2/#4-of-agent_task_event_analytics) runs exactly as it always
    would -- this class adds no shortcut around any of them.

    Stale preflights are handled via Commit #7's own revalidation, not a
    second staleness check (Rule: "Handle stale preflights by using the
    existing revalidation flow"): execute() always calls revalidate()
    first, so a stale/invalidated/superseded starting point is replaced
    with a fresh, current one (or reported blocked, if the fresh one
    itself is not ALLOW) before approval is ever even considered.

    Deterministic and idempotent by delegation (Rule): every underlying
    step is already independently idempotent (Commit #7/#9/#11's own
    "repeat returns the same result" designs) -- calling execute() twice
    in a row with nothing changed in between naturally returns the same
    approval/authorization/consumption records, since none of the
    services it calls do anything different on a repeat call.
    """

    def __init__(
        self,
        revalidation_service: LLMAgentTaskRecoveryPreflightRevalidationService = None,
        approval_service: LLMAgentTaskRecoveryPreflightApprovalService = None,
        authorization_service: LLMAgentTaskRecoveryPreflightAuthorizationService = None,
        validation_service: LLMAgentTaskRecoveryPreflightAuthorizationValidationService = None,
        consumption_service: LLMAgentTaskRecoveryPreflightAuthorizationConsumptionService = None,
    ):
        self._revalidation_service = (
            revalidation_service if revalidation_service is not None else LLMAgentTaskRecoveryPreflightRevalidationService()
        )
        self._approval_service = (
            approval_service if approval_service is not None else LLMAgentTaskRecoveryPreflightApprovalService()
        )
        self._authorization_service = (
            authorization_service
            if authorization_service is not None
            else LLMAgentTaskRecoveryPreflightAuthorizationService()
        )
        self._validation_service = (
            validation_service
            if validation_service is not None
            else LLMAgentTaskRecoveryPreflightAuthorizationValidationService()
        )
        self._consumption_service = (
            consumption_service
            if consumption_service is not None
            else LLMAgentTaskRecoveryPreflightAuthorizationConsumptionService()
        )

    def execute(self, task_id: str, preflight_id: str = None) -> AgentTaskRecoveryOrchestrationResult:
        """Run the full preflight -> approval -> authorization ->
        validation -> consumption lifecycle for task_id, optionally
        asserting preflight_id is the one currently on record (Commit #7's
        own convention: a mismatch raises rather than guessing).

        Never raises for a failed GATE (approval/validation/authorize/
        consume) -- those are reported as executed=False with their own
        blocking_reasons. Only raises for malformed arguments.

        Raises:
            InvalidAgentTaskRecoveryOrchestrationError: If task_id is not
                a non-empty string, or preflight_id is given and is not a
                non-empty string
        """
        self._require_text(task_id, "task_id")
        if preflight_id is not None:
            self._require_text(preflight_id, "preflight_id")

        try:
            revalidation = self._revalidation_service.revalidate(task_id, preflight_id=preflight_id)
        except Exception as error:
            return self._blocked(task_id, preflight_id, None, f"could not resolve a current preflight: {error}")

        original_preflight_id = revalidation.previous_preflight_id
        current_preflight_id = revalidation.current_preflight_id

        if revalidation.decision != ALLOW:
            return self._blocked(
                task_id, original_preflight_id, current_preflight_id,
                f"current preflight decision is {revalidation.decision!r}, not {ALLOW!r}",
            )

        approval = self._approval_service.get(task_id, current_preflight_id)
        if approval is None or approval.status != APPROVED:
            return self._blocked(
                task_id, original_preflight_id, current_preflight_id,
                "preflight has not been approved",
                approval=approval,
            )

        try:
            authorization = self._authorization_service.authorize(task_id, current_preflight_id)
        except Exception as error:
            return self._blocked(
                task_id, original_preflight_id, current_preflight_id,
                f"authorization failed: {error}",
                approval=approval,
            )

        validation = self._validation_service.validate(task_id, authorization.authorization_id)
        if not validation.valid:
            return self._blocked(
                task_id, original_preflight_id, current_preflight_id,
                "; ".join(validation.blocking_reasons),
                approval=approval, authorization=authorization, validation=validation,
            )

        try:
            consumption = self._consumption_service.consume(task_id, authorization.authorization_id)
        except Exception as error:
            return self._blocked(
                task_id, original_preflight_id, current_preflight_id,
                f"consumption failed: {error}",
                approval=approval, authorization=authorization, validation=validation,
            )

        return AgentTaskRecoveryOrchestrationResult(
            task_id=task_id, original_preflight_id=original_preflight_id, current_preflight_id=current_preflight_id,
            approval=approval, authorization=authorization, validation=validation, consumption=consumption,
            executed=True, outcome=consumption.outcome, blocking_reasons=(),
        )

    @staticmethod
    def _blocked(
        task_id, original_preflight_id, current_preflight_id, reason,
        approval=None, authorization=None, validation=None,
    ) -> AgentTaskRecoveryOrchestrationResult:
        return AgentTaskRecoveryOrchestrationResult(
            task_id=task_id, original_preflight_id=original_preflight_id, current_preflight_id=current_preflight_id,
            approval=approval, authorization=authorization, validation=validation, consumption=None,
            executed=False, outcome="blocked", blocking_reasons=(reason,),
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryOrchestrationError(f"{field_name} is required and must be a non-empty string")
