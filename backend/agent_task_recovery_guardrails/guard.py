from backend.agent_task_event_analytics import (
    RECOVERY_ACTION_RETRY,
    RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
    AgentTaskFailureRecoveryPlan,
    LLMAgentTaskEventFailureClassifier,
)
from backend.agent_task_events import LLMAgentTaskEventReplayService
from backend.agent_task_lifecycle import COMPLETED, TERMINAL_STATES
from backend.agent_task_queue_dead_letter import LLMAgentTaskDeadLetterService
from backend.agent_task_queue_reservation import LLMAgentTaskQueueReservationService
from backend.agent_task_queue_retry_eligibility import LLMAgentTaskQueueRetryEligibilityService
from backend.agent_task_queue_retry_scheduler import SCHEDULED, LLMAgentTaskRetryScheduler
from backend.agent_task_readiness import LLMAgentTaskReadinessService

from .models import AgentTaskRecoveryGuardResult


class InvalidAgentTaskRecoveryGuardError(ValueError):
    """Raised when validate() is given invalid arguments."""


class LLMAgentTaskRecoveryGuardService:
    """A pre-execution safety layer for Commit #3(-of-agent_task_event_
    analytics)'s own AgentTaskFailureRecoveryPlan -- sits between planning
    and Commit #4's own LLMAgentTaskFailureRecoveryService.execute_plan(),
    never itself a second policy engine or a second execution path (Rule:
    "Do not invent a second policy engine"; "Do not duplicate Commit #4
    recovery execution"): validate() never calls schedule_retry()/
    enqueue()/refresh()/apply()/dead_letter() or any other mutating method
    on anything -- every check here is a read-only call into an already-
    existing, already-established service this same task-recovery domain
    already relies on elsewhere.

    Re-evaluates current state rather than trusting the plan it is given
    (Rule: "Re-evaluate current state rather than trusting an old plan"):
    every check re-reads live state through its own collaborator at
    validate()-time -- the plan itself is only ever compared against that
    fresh evidence, never assumed correct because it was computed
    earlier (a plan can go stale between being produced and being acted
    on, exactly the scenario this whole guard exists to catch).

    Every collaborator but `classifier`/`replay_service` is optional and
    never internally default-constructed (the same "duck-typed, used
    only if given" shape Commit #3's own planner already establishes for
    `readiness_service`/`context_service`/`retry_eligibility_service`):
    `LLMAgentTaskReadinessService`/`LLMAgentTaskQueueRetryEligibilityService`/
    `LLMAgentTaskRetryScheduler`/`LLMAgentTaskDeadLetterService`/
    `LLMAgentTaskQueueReservationService` all require real, non-optional
    constructor dependencies of their own (a lifecycle/queue service),
    so none of them can be silently default-constructed into a
    meaningless, disconnected instance the way `classifier`/
    `replay_service` safely can (both already default-construct a fresh,
    standalone `LLMAgentTaskEventQueryService()`, the same convention
    every other read-only analytics service in this project's own task
    family already follows). Omitting an optional collaborator simply
    means the condition(s) it backs are never added to
    checked_conditions -- never fabricated as passing (Rule: "Unsupported
    checks must not be fabricated").

    Reuses real, already-established signals for each condition rather
    than inventing new ones (found by inspecting this repository, not
    guessed):
      task eligibility -> backend.agent_task_events.
        LLMAgentTaskEventReplayService.replay().final_state (the same
        event-sourced "current state" source this whole
        agent_task_event_analytics series already relies on throughout,
        never backend.agent_task_lifecycle's own store directly) plus,
        when supplied, backend.agent_task_queue_dead_letter.
        LLMAgentTaskDeadLetterService.get() (already dead-lettered ->
        no further recovery)
      action permission -> backend.agent_task_readiness.
        LLMAgentTaskReadinessService.check()'s own "policy" named check
        (that service already wires backend.agent_policy_enforcement
        internally for exactly this question -- Rule: "Do not invent a
        second policy engine" is honored by reading that existing
        answer, never re-asking backend.agent_policy_enforcement a
        second, independent way)
      retry/budget limits -> backend.agent_task_queue_retry_eligibility.
        LLMAgentTaskQueueRetryEligibilityService.check() (this
        repository's one real "retry attempt budget" concept for a
        task_id; backend.agent_execution_budget was inspected and found
        scoped to a plan execution's own execution_id, a different
        identity space this task-recovery domain does not share --
        checked only when the plan's own action is RECOVERY_ACTION_RETRY,
        the one action this eligibility concept actually governs)
      dependencies/readiness -> the SAME readiness check() call's own
        "dependencies" named check (Commit #3's own planner already
        reads this identical check for the identical reason)
      plan freshness -> a fresh backend.agent_task_event_analytics.
        LLMAgentTaskEventFailureClassifier.classify() call, compared
        against the plan's own failure_event_id/failure_category (Rule:
        "Re-evaluate current state rather than trusting an old plan",
        applied literally)
      conflicting active recovery -> backend.agent_task_queue_retry_scheduler.
        LLMAgentTaskRetryScheduler.get_retry_schedule() (a still-SCHEDULED
        retry is this repository's one genuinely persistent "not yet
        resolved" recovery state -- Commit #4's own execution is fully
        synchronous and leaves no other in-flight state to check) and,
        when supplied, backend.agent_task_queue_reservation.
        LLMAgentTaskQueueReservationService.is_reservation_valid() (a
        worker currently holding a live claim on the task)

    An unresolved "dependencies" check is a WARNING, not a violation,
    specifically for RECOVERY_ACTION_WAIT_FOR_DEPENDENCY (that is exactly
    the condition the plan already exists to wait out -- Commit #4's own
    execution of that action already re-checks readiness and reports a
    graceful, non-crashing failure on its own when still blocked); for
    every other action, the same unresolved dependency is a genuine
    VIOLATION, since that action's own mechanism assumes the task is
    otherwise runnable.

    Deterministic (Rule): every collaborator here is already deterministic
    over its own fixed input, and validate() is a pure function of their
    combined output -- calling it twice in a row with nothing changed in
    between always returns an identical result.
    """

    def __init__(
        self,
        classifier: LLMAgentTaskEventFailureClassifier = None,
        replay_service: LLMAgentTaskEventReplayService = None,
        readiness_service: LLMAgentTaskReadinessService = None,
        retry_eligibility_service: LLMAgentTaskQueueRetryEligibilityService = None,
        retry_scheduler: LLMAgentTaskRetryScheduler = None,
        dead_letter_service: LLMAgentTaskDeadLetterService = None,
        reservation_service: LLMAgentTaskQueueReservationService = None,
    ):
        self._classifier = classifier if classifier is not None else LLMAgentTaskEventFailureClassifier()
        self._replay_service = replay_service if replay_service is not None else LLMAgentTaskEventReplayService()
        self._readiness_service = readiness_service
        self._retry_eligibility_service = retry_eligibility_service
        self._retry_scheduler = retry_scheduler
        self._dead_letter_service = dead_letter_service
        self._reservation_service = reservation_service

    def validate(self, task_id: str, recovery_plan: AgentTaskFailureRecoveryPlan) -> AgentTaskRecoveryGuardResult:
        """Check recovery_plan against task_id's own CURRENT, freshly
        re-read state, never against whatever was true when the plan was
        computed.

        Raises:
            InvalidAgentTaskRecoveryGuardError: If task_id is not a
                non-empty string, recovery_plan is not an
                AgentTaskFailureRecoveryPlan, or recovery_plan.task_id
                does not match task_id
        """
        self._require_text(task_id)
        if not isinstance(recovery_plan, AgentTaskFailureRecoveryPlan):
            raise InvalidAgentTaskRecoveryGuardError("recovery_plan must be an AgentTaskFailureRecoveryPlan")
        if recovery_plan.task_id != task_id:
            raise InvalidAgentTaskRecoveryGuardError(
                f"recovery_plan.task_id {recovery_plan.task_id!r} does not match task_id {task_id!r}"
            )

        violations: list = []
        warnings: list = []
        checked_conditions: list = []

        self._check_task_eligibility(task_id, violations, checked_conditions)
        self._check_plan_freshness(task_id, recovery_plan, violations, checked_conditions)

        readiness_result = None
        if self._readiness_service is not None:
            readiness_result = self._readiness_service.check(task_id)
        self._check_action_permission(readiness_result, violations, checked_conditions)
        self._check_retry_budget(task_id, recovery_plan.recommended_action, violations, checked_conditions)
        self._check_dependency_readiness(
            readiness_result, recovery_plan.recommended_action, violations, warnings, checked_conditions
        )
        self._check_conflicting_recovery(task_id, violations, checked_conditions)

        return AgentTaskRecoveryGuardResult(
            task_id=task_id,
            recommended_action=recovery_plan.recommended_action,
            allowed=not violations,
            violations=tuple(violations),
            warnings=tuple(warnings),
            checked_conditions=tuple(checked_conditions),
        )

    def _check_task_eligibility(self, task_id: str, violations: list, checked_conditions: list) -> None:
        checked_conditions.append("task_eligibility")
        current_state = self._replay_service.replay(task_id).final_state

        if current_state == COMPLETED:
            violations.append("task has already completed successfully; recovery is no longer applicable")
        elif current_state not in TERMINAL_STATES:
            violations.append(
                f"task is not currently in a failed/cancelled state (current state: {current_state!r}); "
                "recovery is not applicable"
            )

        if self._dead_letter_service is not None:
            checked_conditions.append("dead_letter_status")
            if self._dead_letter_service.get(task_id) is not None:
                violations.append("task has already been dead-lettered; no further recovery is permitted")

    def _check_plan_freshness(
        self, task_id: str, recovery_plan: AgentTaskFailureRecoveryPlan, violations: list, checked_conditions: list
    ) -> None:
        checked_conditions.append("plan_freshness")
        classification = self._classifier.classify(task_id)
        current_failure = classification.terminal_failure
        if current_failure is None and classification.failures:
            current_failure = classification.failures[-1]

        if current_failure is None:
            if recovery_plan.failure_event_id is not None:
                violations.append("plan references a failure that no longer appears in the task's own history")
            return

        if recovery_plan.failure_event_id != current_failure.event_id:
            violations.append(
                f"plan is stale: it was built for failure_event_id {recovery_plan.failure_event_id!r}, "
                f"but the task's current failure is {current_failure.event_id!r}"
            )
        elif recovery_plan.failure_category != current_failure.category:
            violations.append(
                f"plan is stale: failure_category has changed from {recovery_plan.failure_category!r} "
                f"to {current_failure.category!r}"
            )

    @staticmethod
    def _check_action_permission(readiness_result, violations: list, checked_conditions: list) -> None:
        if readiness_result is None:
            return
        policy_check = next((check for check in readiness_result.checks if check.name == "policy"), None)
        if policy_check is None:
            return
        checked_conditions.append("action_permission")
        if not policy_check.passed:
            violations.append(f"requested action is not currently permitted: {policy_check.detail}")

    def _check_retry_budget(self, task_id: str, action: str, violations: list, checked_conditions: list) -> None:
        if action != RECOVERY_ACTION_RETRY or self._retry_eligibility_service is None:
            return
        checked_conditions.append("retry_budget")
        eligibility = self._retry_eligibility_service.check(task_id)
        if not eligibility.eligible:
            violations.append(f"retry is not currently eligible: {eligibility.reason}")

    @staticmethod
    def _check_dependency_readiness(
        readiness_result, action: str, violations: list, warnings: list, checked_conditions: list
    ) -> None:
        if readiness_result is None:
            return
        dependency_check = next((check for check in readiness_result.checks if check.name == "dependencies"), None)
        if dependency_check is None:
            return
        checked_conditions.append("dependency_readiness")
        if dependency_check.passed:
            return
        if action == RECOVERY_ACTION_WAIT_FOR_DEPENDENCY:
            warnings.append(f"dependencies are still unresolved: {dependency_check.detail}")
        else:
            violations.append(
                f"requested action requires resolved dependencies, but they are not resolved: "
                f"{dependency_check.detail}"
            )

    def _check_conflicting_recovery(self, task_id: str, violations: list, checked_conditions: list) -> None:
        if self._retry_scheduler is not None:
            checked_conditions.append("conflicting_recovery")
            schedule = self._retry_scheduler.get_retry_schedule(task_id)
            if schedule is not None and schedule.status == SCHEDULED:
                violations.append(
                    f"a retry (attempt {schedule.attempt}) is already scheduled for this task; "
                    "this recovery action would conflict with it"
                )

        if self._reservation_service is not None:
            checked_conditions.append("active_reservation")
            if self._reservation_service.is_reservation_valid(task_id):
                violations.append(
                    "task is currently held by an active reservation; a conflicting recovery attempt "
                    "would race with it"
                )

    @staticmethod
    def _require_text(value, field_name: str = "task_id") -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryGuardError(f"{field_name} is required and must be a non-empty string")
