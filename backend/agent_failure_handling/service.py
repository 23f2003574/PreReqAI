from backend.llm.tool_execution import DENIED, SUCCEEDED
from backend.llm.tool_retry import NEVER_RETRYABLE_STATUSES

from .models import (
    BLOCK,
    CONTINUE,
    DEPENDENCY_FAILURE,
    FAIL,
    NONE,
    PERMANENT,
    PERMISSION_DENIED,
    RETRY,
    RETRYABLE,
    LLMAgentFailureClassification,
)

_ACTION_FOR_CATEGORY = {
    NONE: CONTINUE,
    RETRYABLE: RETRY,
    PERMANENT: FAIL,
    PERMISSION_DENIED: FAIL,
    DEPENDENCY_FAILURE: BLOCK,
}


class UnknownFailureStepError(KeyError):
    """Raised when classify()/next_action()/can_continue() names a step_id not in the plan."""


class LLMAgentFailureService:
    """Decides what should happen next for one step, from what already happened.

    Not another workflow or recovery engine: this service runs nothing and
    holds no state of its own. It only reads Commit #1's plan, Commit #3's
    own execution records, and asks the existing
    backend.llm.tool_retry.LLMToolRetryService whether a failure's own
    error is one the wired retry policy already treats as retryable --
    the exact same classification that pipeline already applied (or would
    apply) to this call, never a second copy of it. Deciding to actually
    retry, recover, or otherwise act on that decision is still entirely
    Commit #3/#4/#6's job; this service only tells a caller which of
    RETRY, CONTINUE, BLOCK, or FAIL applies.

    classify() is the diagnostic: which of CATEGORIES a step is currently
    in, and why, in its own words (the step's recorded status/error,
    verbatim). next_action() maps that category onto one of the four
    actions. can_continue() is next_action() reduced to a boolean --
    CONTINUE or RETRY mean the plan is not necessarily doomed by this
    step; BLOCK or FAIL mean it is, for this step and everything that
    depends on it.

    Precedence, checked in this order:

        1. a dependency that did not SUCCEED blocks this step outright,
           whether or not this step has been attempted at all
        2. DENIED (Commit #4 authorization refused it) is a security
           decision, never retried, whatever the retry policy says
        3. everything else the wired LLMToolRetryService says is
           retryable, is RETRYABLE
        4. everything else that recorded a non-SUCCEEDED outcome is a
           PERMANENT failure
        5. no recorded outcome at all, or SUCCEEDED, is NONE -- CONTINUE
    """

    def __init__(self, planning_service, step_execution_service, retry_service, plan_execution_service=None):
        self._planning_service = planning_service
        self._step_execution_service = step_execution_service
        self._retry_service = retry_service
        self._plan_execution_service = plan_execution_service

    def _plan(self, execution_id: str):
        if self._plan_execution_service is not None:
            plan_id = self._plan_execution_service.get(execution_id).plan_id
        else:
            plan_id = execution_id
        return self._planning_service.get(plan_id)

    @staticmethod
    def _find_step(plan, step_id: str):
        for step in plan.steps:
            if step.step_id == step_id:
                return step
        raise UnknownFailureStepError(step_id)

    def _executions_by_step(self, plan_id: str) -> dict:
        """The latest recorded execution per step_id. Absent means never attempted."""
        latest = {}
        for record in self._step_execution_service.executions(plan_id):
            latest[record.step_id] = record
        return latest

    def _is_retryable(self, step_execution) -> bool:
        """Whether the wired retry policy already treats this failure as retryable.

        A gate refusal is never retryable, whatever the policy says --
        checked first, independent of should_retry(). Beyond that, the
        status (matches an explicitly retryable status like TIMED_OUT) and
        the error text (matches a retryable exception's class name, the
        "ClassName: detail" shape Commit #5 already records) are both
        checked, since should_retry() only recognizes one shape per call.
        """
        if step_execution.status in NEVER_RETRYABLE_STATUSES:
            return False
        return self._retry_service.should_retry(
            step_execution.status
        ) or self._retry_service.should_retry(step_execution.error)

    def classify(self, execution_id: str, step_id: str) -> LLMAgentFailureClassification:
        plan = self._plan(execution_id)
        step = self._find_step(plan, step_id)
        executions = self._executions_by_step(plan.plan_id)

        failed_dependency = next(
            (
                dependency for dependency in step.depends_on
                if dependency not in executions or executions[dependency].status != SUCCEEDED
            ),
            None,
        )
        if failed_dependency is not None:
            dependency_status = (
                executions[failed_dependency].status if failed_dependency in executions else "not yet attempted"
            )
            return LLMAgentFailureClassification(
                step_id=step_id,
                category=DEPENDENCY_FAILURE,
                reason=f"depends on step {failed_dependency!r}, which is {dependency_status}",
            )

        step_execution = executions.get(step_id)
        if step_execution is None or step_execution.status == SUCCEEDED:
            return LLMAgentFailureClassification(step_id=step_id, category=NONE, reason="no failure recorded")

        if step_execution.status == DENIED:
            return LLMAgentFailureClassification(
                step_id=step_id,
                category=PERMISSION_DENIED,
                reason=step_execution.error or "denied by permission policy",
            )

        if self._is_retryable(step_execution):
            return LLMAgentFailureClassification(
                step_id=step_id, category=RETRYABLE, reason=step_execution.error or step_execution.status
            )

        return LLMAgentFailureClassification(
            step_id=step_id, category=PERMANENT, reason=step_execution.error or step_execution.status
        )

    def next_action(self, execution_id: str, step_id: str) -> str:
        return _ACTION_FOR_CATEGORY[self.classify(execution_id, step_id).category]

    def can_continue(self, execution_id: str, step_id: str) -> bool:
        return self.next_action(execution_id, step_id) in (CONTINUE, RETRY)
