from backend.agent_policy_engine import DENY
from backend.agent_task_event_analytics import (
    RECOVERY_ACTION_RETRY,
    RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
    LLMAgentTaskEventFailureClassifier,
)
from backend.agent_task_events import LLMAgentTaskEventReplayService
from backend.agent_task_queue_retry_eligibility import LLMAgentTaskQueueRetryEligibilityService
from backend.agent_task_readiness import LLMAgentTaskReadinessService

from .models import AgentTaskRecoveryPreflight, AgentTaskRecoveryPreflightFreshness
from .preflight_store import LLMAgentTaskRecoveryPreflightStore


class InvalidAgentTaskRecoveryPreflightFreshnessError(ValueError):
    """Raised when check() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightFreshnessService:
    """Detects when a Commit #4 stored AgentTaskRecoveryPreflight is no
    longer trustworthy, because the task or recovery conditions have
    changed since it was checked -- never a second cache/freshness
    framework (Rule) and never a second guard evaluation (Rule: "Do not
    duplicate Commit #1 guard checks"): check() never calls Commit #1's
    own LLMAgentTaskRecoveryGuardService.validate() or Commit #2's own
    evaluate(), and never re-derives an ALLOW/DENY/REVIEW verdict -- it
    only ever compares a small, fixed set of reference facts against what
    the stored preflight itself recorded or implied.

    Read-only, never executes (Rule: "Read-only"; "Never rerun
    recovery"): every collaborator this service calls is one of its own
    already-read-only checks (classify()/replay()/check()) -- nothing
    here calls plan()/execute()/schedule_retry()/dead_letter() or any
    other mutating method.

    Three independent comparisons, each reusing an existing interface
    directly rather than re-deriving a guard verdict:

      task state/version -> backend.agent_task_events.
        LLMAgentTaskEventReplayService.replay(), called twice: once
        bounded to `end_time=preflight.checked_at` (reconstructing what
        the task's own state WAS at preflight time -- the append-only
        event log's own natural "version" mechanism, reused rather than
        inventing a version counter of its own) and once unbounded (the
        real current state). A mismatch is direct evidence the task's
        own authoritative state has moved on.

      recovery plan identity/source failure event -> a fresh backend.
        agent_task_event_analytics.LLMAgentTaskEventFailureClassifier.
        classify() call, compared against the stored plan's own
        failure_event_id/failure_category -- the same comparison Commit
        #1's own "plan_freshness" guard check makes, but here comparing
        a STORED, already-persisted snapshot against the present moment
        (a fundamentally different, retrospective question from Commit
        #1's own "is this in-memory plan, about to be executed right
        now, still valid" check on a plan that was never persisted at
        all) rather than a second implementation of the same idea.

      relevant retry/dependency/readiness conditions -> only the ones
      the stored plan's own recommended_action actually depends on
      (mirrors Commit #1's own "only check retry_budget for RETRY, only
      warn on dependencies for WAIT_FOR_DEPENDENCY" scoping exactly):
      RECOVERY_ACTION_WAIT_FOR_DEPENDENCY checks whether the SAME
      "dependencies" named readiness check has since started passing
      (the wait condition resolved -- the plan is now stale advice, not
      still-correct guidance); RECOVERY_ACTION_RETRY checks whether
      backend.agent_task_queue_retry_eligibility.
      LLMAgentTaskQueueRetryEligibilityService.check() still reports
      eligible; every action checks the SAME "policy" named readiness
      check the same way Commit #1 already does for "action_permission",
      since a permission change is relevant regardless of which specific
      action was recommended. Both the policy and retry checks only flag
      a CURRENT failure as newly stale when the stored preflight's own
      decision was not already backend.agent_policy_engine.DENY: a
      preflight that already correctly denies for the SAME underlying
      class of reason has nothing NEW to report, and re-flagging it every
      single call would make revalidation (a later commit's own concern)
      never converge -- the stored decision, not just the bare current
      readiness/retry answer, is part of what "still accounted for"
      means here.

    Every optional collaborator (readiness_service/
    retry_eligibility_service) follows the exact same "duck-typed, used
    only if given, never internally default-constructed" shape Commit #1
    already establishes (neither service can be zero-arg constructed) --
    but unlike Commit #1's own guard, an APPLICABLE-but-unverifiable
    condition here is never simply absent from the result: it is reported
    as its own stale_reasons entry (Rule: "Never silently treat missing
    evidence as fresh" -- the same discipline Commit #2's own "never
    silently convert an unknown condition into allow" already
    establishes for a structurally identical problem), since silently
    omitting it would let is_fresh default to True precisely when this
    service has the least ability to actually confirm that.

    Deterministic (Rule): every collaborator here is already
    deterministic over its own fixed input (classify()/replay()/check()
    are all pure reads), and check() is a pure function of their combined
    output -- calling it twice in a row with nothing changed in between
    always returns an identical result.
    """

    def __init__(
        self,
        preflight_store: LLMAgentTaskRecoveryPreflightStore = None,
        classifier: LLMAgentTaskEventFailureClassifier = None,
        replay_service: LLMAgentTaskEventReplayService = None,
        readiness_service: LLMAgentTaskReadinessService = None,
        retry_eligibility_service: LLMAgentTaskQueueRetryEligibilityService = None,
    ):
        self._preflight_store = (
            preflight_store if preflight_store is not None else LLMAgentTaskRecoveryPreflightStore()
        )
        self._classifier = classifier if classifier is not None else LLMAgentTaskEventFailureClassifier()
        self._replay_service = replay_service if replay_service is not None else LLMAgentTaskEventReplayService()
        self._readiness_service = readiness_service
        self._retry_eligibility_service = retry_eligibility_service

    def check(self, task_id: str, preflight: AgentTaskRecoveryPreflight = None) -> AgentTaskRecoveryPreflightFreshness:
        """Check whether task_id's stored preflight (or the given one,
        when supplied directly instead of looked up) is still fresh.

        Never fresh when no preflight exists at all to compare against
        (Rule: "Never silently treat missing evidence as fresh") --
        there is nothing here that could have earned a "fresh" verdict.

        Raises:
            InvalidAgentTaskRecoveryPreflightFreshnessError: If task_id is
                not a non-empty string, preflight is given and is not an
                AgentTaskRecoveryPreflight, or preflight.task_id does not
                match task_id
        """
        self._require_text(task_id)
        if preflight is not None:
            if not isinstance(preflight, AgentTaskRecoveryPreflight):
                raise InvalidAgentTaskRecoveryPreflightFreshnessError(
                    "preflight must be an AgentTaskRecoveryPreflight"
                )
            if preflight.task_id != task_id:
                raise InvalidAgentTaskRecoveryPreflightFreshnessError(
                    f"preflight.task_id {preflight.task_id!r} does not match task_id {task_id!r}"
                )
        else:
            preflight = self._preflight_store.get(task_id)

        if preflight is None:
            return AgentTaskRecoveryPreflightFreshness(
                task_id=task_id,
                is_fresh=False,
                stale_reasons=("no stored preflight is recorded for this task",),
                checked_references=(),
            )

        stale_reasons: list = []
        checked_references: list = []

        self._check_task_state(task_id, preflight, stale_reasons, checked_references)
        self._check_plan_identity(task_id, preflight, stale_reasons, checked_references)
        self._check_relevant_conditions(task_id, preflight, stale_reasons, checked_references)

        return AgentTaskRecoveryPreflightFreshness(
            task_id=task_id,
            is_fresh=not stale_reasons,
            stale_reasons=tuple(stale_reasons),
            checked_references=tuple(checked_references),
        )

    def _check_task_state(self, task_id: str, preflight, stale_reasons: list, checked_references: list) -> None:
        checked_references.append("task_state")
        state_at_checkpoint = self._replay_service.replay(task_id, end_time=preflight.checked_at).final_state
        current_state = self._replay_service.replay(task_id).final_state
        if state_at_checkpoint != current_state:
            stale_reasons.append(
                f"task state changed from {state_at_checkpoint!r} to {current_state!r} "
                "since this preflight was checked"
            )

    def _check_plan_identity(self, task_id: str, preflight, stale_reasons: list, checked_references: list) -> None:
        if preflight.plan is None:
            return
        checked_references.append("plan_identity")

        classification = self._classifier.classify(task_id)
        current_failure = classification.terminal_failure
        if current_failure is None and classification.failures:
            current_failure = classification.failures[-1]

        if current_failure is None:
            if preflight.plan.failure_event_id is not None:
                stale_reasons.append("the plan's own source failure no longer appears in the task's history")
            return

        if preflight.plan.failure_event_id != current_failure.event_id:
            stale_reasons.append(
                f"the plan's own source failure_event_id {preflight.plan.failure_event_id!r} no longer "
                f"matches the task's current failure {current_failure.event_id!r}"
            )
        elif preflight.plan.failure_category != current_failure.category:
            stale_reasons.append(
                f"the failure_category has changed from {preflight.plan.failure_category!r} to "
                f"{current_failure.category!r} since this preflight was checked"
            )

    def _check_relevant_conditions(self, task_id: str, preflight, stale_reasons: list, checked_references: list) -> None:
        action = preflight.plan.recommended_action if preflight.plan is not None else None

        if self._readiness_service is None:
            stale_reasons.append("action permission could not be verified: no readiness_service was supplied")
        else:
            readiness_result = self._readiness_service.check(task_id)

            policy_check = next((check for check in readiness_result.checks if check.name == "policy"), None)
            if policy_check is not None:
                checked_references.append("action_permission")
                if not policy_check.passed and preflight.decision != DENY:
                    stale_reasons.append(f"the action is no longer permitted: {policy_check.detail}")

            if action == RECOVERY_ACTION_WAIT_FOR_DEPENDENCY:
                dependency_check = next(
                    (check for check in readiness_result.checks if check.name == "dependencies"), None
                )
                if dependency_check is not None:
                    checked_references.append("dependency_condition")
                    if dependency_check.passed:
                        stale_reasons.append(
                            "the dependency condition that justified waiting has been resolved "
                            "since this preflight was checked"
                        )

        if action == RECOVERY_ACTION_RETRY:
            if self._retry_eligibility_service is None:
                stale_reasons.append(
                    "retry eligibility could not be verified: no retry_eligibility_service was supplied"
                )
            else:
                checked_references.append("retry_condition")
                eligibility = self._retry_eligibility_service.check(task_id)
                if not eligibility.eligible and preflight.decision != DENY:
                    stale_reasons.append(
                        f"retry eligibility has changed since this preflight was checked: {eligibility.reason}"
                    )

    @staticmethod
    def _require_text(value, field_name: str = "task_id") -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightFreshnessError(
                f"{field_name} is required and must be a non-empty string"
            )
