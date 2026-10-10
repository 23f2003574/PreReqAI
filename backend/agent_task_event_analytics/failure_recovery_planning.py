from backend.agent_task_context import LLMAgentTaskContextService, UnknownTaskContextError
from backend.agent_task_queue_retry_eligibility import LLMAgentTaskQueueRetryEligibilityService
from backend.agent_task_queue_retry_repair import LLMAgentTaskRetryRepairService
from backend.agent_task_readiness import LLMAgentTaskReadinessService

from .failure_classification import LLMAgentTaskEventFailureClassifier
from .models import (
    FAILURE_CATEGORY_CONTEXT,
    FAILURE_CATEGORY_DEPENDENCY,
    FAILURE_CATEGORY_EXECUTION,
    FAILURE_CATEGORY_RETRY_EXHAUSTION,
    FAILURE_CATEGORY_TIMEOUT_CANCELLATION,
    FAILURE_CATEGORY_VALIDATION_POLICY,
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_NONE,
    RECOVERY_ACTION_REFRESH_CONTEXT,
    RECOVERY_ACTION_REPAIR_TASK,
    RECOVERY_ACTION_RETRY,
    RECOVERY_ACTION_UNRESOLVED,
    RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
    RECOVERY_PRIORITY_HIGH,
    RECOVERY_PRIORITY_LOW,
    RECOVERY_PRIORITY_MEDIUM,
    RECOVERY_PRIORITY_NONE,
    AgentTaskFailureRecoveryPlan,
)


class InvalidAgentTaskFailureRecoveryPlanError(ValueError):
    """Raised when plan() is given invalid arguments."""


class LLMAgentTaskEventFailureRecoveryPlanner:
    """Turns Commit #2's own classified failures into one concrete
    recovery recommendation -- planning only (Rule: "Never execute
    recovery"): nothing here ever calls a retry/readiness/context/repair
    service's own mutating method, only its read-only checks.

    Never reclassifies (Rule: "Reuse Commit #2 classification rather than
    reclassifying failures"): plan() calls LLMAgentTaskEventFailureClassifier.
    classify() exactly once and only ever reads its own
    failure_category/event_id/reason back -- it never re-derives a
    category from raw events itself.

    Never invents a recovery mechanism (Rule: "Do not invent new recovery
    mechanisms"; "Never invent an action merely to fill a result"): every
    action this planner can recommend is backed by an existing, already-
    read-only-callable service (see .models.RECOVERY_ACTIONS's own
    docstring for the exact mapping) -- when the collaborator needed to
    verify a category's own action is not supplied, or none of its checks
    point anywhere specific, the result is RECOVERY_ACTION_UNRESOLVED,
    never a guess.

    Every collaborator is optional (the same "duck-typed, used only if
    given" shape this project's own services already use throughout):
    omitting one simply means that category's own feasibility can never
    be confirmed, so it resolves to UNRESOLVED rather than a wrong guess.

    "Conflicting recovery signals" are resolved by trusting the *current*,
    live state of an existing service over Commit #2's own *historical*
    classification for deciding the action (though never for the
    category itself, which always stays exactly what Commit #2 reported):
    a failure classified "dependency" whose backend.agent_task_readiness
    own "dependencies" check now passes is no longer actually blocked, so
    RECOVERY_ACTION_RETRY is recommended instead of
    RECOVERY_ACTION_WAIT_FOR_DEPENDENCY -- recommending a wait that would
    never end is exactly the kind of "mutually incompatible"/stale
    recommendation Rule: "avoid recommending mutually incompatible
    actions" warns against.

    Deterministic (Rule): classify()'s own output is already deterministic,
    and every read-only collaborator check here is a pure function of
    current state -- calling plan() twice in a row with nothing changed in
    between always returns an identical result.
    """

    def __init__(
        self,
        classifier: LLMAgentTaskEventFailureClassifier = None,
        readiness_service: LLMAgentTaskReadinessService = None,
        context_service: LLMAgentTaskContextService = None,
        retry_eligibility_service: LLMAgentTaskQueueRetryEligibilityService = None,
        retry_repair_service: LLMAgentTaskRetryRepairService = None,
    ):
        self._classifier = classifier if classifier is not None else LLMAgentTaskEventFailureClassifier()
        self._readiness_service = readiness_service
        self._context_service = context_service
        self._retry_eligibility_service = retry_eligibility_service
        self._retry_repair_service = retry_repair_service

    def plan(self, task_id: str) -> AgentTaskFailureRecoveryPlan:
        """Recommend one concrete recovery action for task_id, based on
        its own classified failure history.

        Raises:
            InvalidAgentTaskFailureRecoveryPlanError: If task_id is not a
                non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskFailureRecoveryPlanError("task_id is required and must be a non-empty string")

        classification = self._classifier.classify(task_id)

        failure = classification.terminal_failure
        if failure is None and classification.failures:
            failure = classification.failures[-1]

        if failure is None:
            return AgentTaskFailureRecoveryPlan(
                task_id=task_id,
                failure_event_id=None,
                failure_category=None,
                recommended_action=RECOVERY_ACTION_NONE,
                reason="no failures found for this task",
                priority=RECOVERY_PRIORITY_NONE,
                blocking_conditions=(),
            )

        action, reason, priority, blocking_conditions = self._plan_for_category(task_id, failure.category)

        return AgentTaskFailureRecoveryPlan(
            task_id=task_id,
            failure_event_id=failure.event_id,
            failure_category=failure.category,
            recommended_action=action,
            reason=reason,
            priority=priority,
            blocking_conditions=blocking_conditions,
        )

    def _plan_for_category(self, task_id: str, category: str):
        if category == FAILURE_CATEGORY_TIMEOUT_CANCELLATION:
            return (
                RECOVERY_ACTION_MARK_UNRECOVERABLE,
                "task was cancelled; cancellation is not automatically retried",
                RECOVERY_PRIORITY_LOW,
                (),
            )

        if category == FAILURE_CATEGORY_DEPENDENCY:
            return self._plan_dependency(task_id)

        if category == FAILURE_CATEGORY_CONTEXT:
            return self._plan_context(task_id)

        if category == FAILURE_CATEGORY_VALIDATION_POLICY:
            return (
                RECOVERY_ACTION_MARK_UNRECOVERABLE,
                "policy/validation failures require manual review; no automated repair exists in this repository",
                RECOVERY_PRIORITY_LOW,
                (),
            )

        if category in (FAILURE_CATEGORY_RETRY_EXHAUSTION, FAILURE_CATEGORY_EXECUTION):
            return self._plan_retryable(task_id)

        return (
            RECOVERY_ACTION_UNRESOLVED,
            f"failure category {category!r} is unsupported; no recovery action can be determined",
            RECOVERY_PRIORITY_LOW,
            (),
        )

    def _plan_dependency(self, task_id: str):
        if self._readiness_service is None:
            return (
                RECOVERY_ACTION_UNRESOLVED,
                "no readiness service was supplied to check dependency status",
                RECOVERY_PRIORITY_LOW,
                (),
            )

        result = self._readiness_service.check(task_id)
        dependency_check = next((check for check in result.checks if check.name == "dependencies"), None)

        if dependency_check is not None and not dependency_check.passed:
            blocking_conditions = tuple(
                reason.strip() for reason in (dependency_check.detail or "").split(";") if reason.strip()
            )
            return (
                RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
                "task is still blocked by unresolved dependencies",
                RECOVERY_PRIORITY_HIGH,
                blocking_conditions,
            )

        # the dependency that originally caused this failure is no longer
        # blocking the task -- waiting further would be stale advice
        return (
            RECOVERY_ACTION_RETRY,
            "the dependency that originally blocked this task is no longer blocking it",
            RECOVERY_PRIORITY_HIGH,
            (),
        )

    def _plan_context(self, task_id: str):
        if self._context_service is None:
            return (
                RECOVERY_ACTION_UNRESOLVED,
                "no context service was supplied to check for a refreshable context record",
                RECOVERY_PRIORITY_LOW,
                (),
            )

        try:
            self._context_service.get(task_id)
        except UnknownTaskContextError:
            return (
                RECOVERY_ACTION_UNRESOLVED,
                "no task context record exists to refresh",
                RECOVERY_PRIORITY_LOW,
                (),
            )

        return (
            RECOVERY_ACTION_REFRESH_CONTEXT,
            "a task context record exists and can be refreshed",
            RECOVERY_PRIORITY_MEDIUM,
            (),
        )

    def _plan_retryable(self, task_id: str):
        if self._retry_repair_service is not None:
            repair_plan = self._retry_repair_service.plan_repair(task_id)
            operation = next(
                (
                    op
                    for op in (repair_plan.schedule_updates + repair_plan.schedules_to_create)
                    if op.task_id == task_id
                ),
                None,
            )
            if operation is not None:
                return (
                    RECOVERY_ACTION_REPAIR_TASK,
                    f"a retry schedule repair is available: {operation.reason}",
                    RECOVERY_PRIORITY_HIGH,
                    (),
                )
            blocked = next((op for op in repair_plan.blocked_repairs if op.task_id == task_id), None)
            if blocked is not None:
                return (
                    RECOVERY_ACTION_MARK_UNRECOVERABLE,
                    f"retry repair is blocked: {blocked.reason}",
                    RECOVERY_PRIORITY_LOW,
                    (),
                )

        if self._retry_eligibility_service is not None:
            eligibility = self._retry_eligibility_service.check(task_id)
            if eligibility.eligible:
                return (
                    RECOVERY_ACTION_RETRY,
                    "retry eligibility check reports the task may retry again",
                    RECOVERY_PRIORITY_HIGH,
                    (),
                )
            if eligibility.dead_letter_required:
                return (
                    RECOVERY_ACTION_MARK_UNRECOVERABLE,
                    f"retry attempts exhausted: {eligibility.reason}",
                    RECOVERY_PRIORITY_LOW,
                    (),
                )
            return (
                RECOVERY_ACTION_UNRESOLVED,
                f"task is not currently retry-eligible: {eligibility.reason}",
                RECOVERY_PRIORITY_LOW,
                (),
            )

        return (
            RECOVERY_ACTION_UNRESOLVED,
            "no retry eligibility or repair service was supplied to verify this",
            RECOVERY_PRIORITY_LOW,
            (),
        )
