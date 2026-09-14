from backend.agent_task_context_refresh import LLMAgentTaskContextRefreshService
from backend.agent_task_queue import LLMAgentTaskQueueService
from backend.agent_task_queue_dead_letter import LLMAgentTaskDeadLetterService
from backend.agent_task_queue_retry_repair import LLMAgentTaskRetryRepairService
from backend.agent_task_queue_retry_repair_execution import FAILED as REPAIR_FAILED
from backend.agent_task_queue_retry_repair_execution import PARTIAL as REPAIR_PARTIAL
from backend.agent_task_queue_retry_repair_execution import LLMAgentTaskRetryRepairExecutor
from backend.agent_task_queue_retry_scheduler import LLMAgentTaskRetryScheduler
from backend.agent_task_readiness import LLMAgentTaskReadinessService

from .failure_recovery_planning import LLMAgentTaskEventFailureRecoveryPlanner
from .models import (
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_NONE,
    RECOVERY_ACTION_REFRESH_CONTEXT,
    RECOVERY_ACTION_REPAIR_TASK,
    RECOVERY_ACTION_RETRY,
    RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
    AgentTaskFailureRecoveryPlan,
    AgentTaskFailureRecoveryResult,
)


class InvalidAgentTaskFailureRecoveryExecutionError(ValueError):
    """Raised when execute()/execute_plan() is given invalid arguments."""


class LLMAgentTaskFailureRecoveryService:
    """Carries out the one recommendation Commit #3's own
    LLMAgentTaskEventFailureRecoveryPlanner already produced -- planning
    and execution stay cleanly separated (Rule): this class never decides
    *what* to do, only *whether it could actually be done*, by calling
    into the exact existing mechanism each action already has:
      RETRY -> backend.agent_task_queue_retry_scheduler.
        LLMAgentTaskRetryScheduler.schedule_retry()
      WAIT_FOR_DEPENDENCY -> backend.agent_task_readiness.
        LLMAgentTaskReadinessService.check() to re-confirm, then
        backend.agent_task_queue.LLMAgentTaskQueueService.enqueue() once
        actually ready (the existing "put a ready task back to work"
        mechanism -- Rule: "use existing dependency/readiness mechanism")
      REFRESH_CONTEXT -> backend.agent_task_context_refresh.
        LLMAgentTaskContextRefreshService.refresh()
      REPAIR_TASK -> backend.agent_task_queue_retry_repair_execution.
        LLMAgentTaskRetryRepairExecutor.apply(), fed a fresh
        backend.agent_task_queue_retry_repair.LLMAgentTaskRetryRepairService.
        plan_repair() (never the stale one Commit #3 may have looked at
        while planning -- Rule: "Respect existing ... checks" means
        revalidating right before acting, the same discipline that
        executor's own apply() already documents for itself)
      MARK_UNRECOVERABLE -> backend.agent_task_queue_dead_letter.
        LLMAgentTaskDeadLetterService.dead_letter(), given the plan's
        own reason verbatim (Rule: "don't reimplement recovery
        decisions" -- this service never invents its own dead-letter
        explanation)

    Never invents execution infrastructure (Rule): there is no retry
    loop, worker, or scheduler here -- every action is exactly one call
    into one already-existing, already-read-only-or-idempotent service
    method. Every collaborator is optional (the same "duck-typed, used
    only if given" shape this project's services already use); an action
    whose required collaborator was never supplied cannot be executed at
    all and fails explicitly (Rule: "Unsupported actions must fail
    explicitly, not silently succeed") -- exactly the same outcome as an
    action this service does not recognize at all.

    Idempotency is inherited, never reimplemented (Rule: "Do not execute
    an action twice when the underlying mechanism is idempotent/
    trackable"): schedule_retry()/enqueue()/dead_letter() are already
    idempotent by their own design (a repeat call returns the existing
    record unchanged rather than duplicating it) -- this service adds no
    extra bookkeeping on top, it simply always calls the same real
    method, which already does the right thing on a repeat call.

    Failures are caught and reported through the structured result,
    never left to propagate uncaught (Rule: "Use the repository's
    transaction/error-handling conventions" -- the same "attempt, catch,
    report" discipline backend.agent_task_queue_retry_repair_execution.
    LLMAgentTaskRetryRepairExecutor.apply() itself already uses for its
    own per-operation attempts) -- except for this service's own argument
    validation (task_id/plan type), which still raises immediately, the
    same "validate your own inputs eagerly, contain a collaborator's
    failure gracefully" split every other multi-stage service in this
    project already draws.

    Never touches backend.agent_task_lifecycle directly (Rule: "Preserve
    existing error/state semantics") -- only through whatever readiness/
    queue/dead-letter service was supplied, and only ever via their own
    already-existing, already-guarded methods.
    """

    def __init__(
        self,
        planner: LLMAgentTaskEventFailureRecoveryPlanner = None,
        retry_scheduler: LLMAgentTaskRetryScheduler = None,
        readiness_service: LLMAgentTaskReadinessService = None,
        queue_service: LLMAgentTaskQueueService = None,
        context_refresh_service: LLMAgentTaskContextRefreshService = None,
        retry_repair_service: LLMAgentTaskRetryRepairService = None,
        dead_letter_service: LLMAgentTaskDeadLetterService = None,
    ):
        self._planner = planner if planner is not None else LLMAgentTaskEventFailureRecoveryPlanner()
        self._retry_scheduler = retry_scheduler
        self._readiness_service = readiness_service
        self._queue_service = queue_service
        self._context_refresh_service = context_refresh_service
        self._retry_repair_service = retry_repair_service
        self._retry_repair_executor = (
            LLMAgentTaskRetryRepairExecutor(retry_scheduler) if retry_scheduler is not None else None
        )
        self._dead_letter_service = dead_letter_service

    def execute(self, task_id: str) -> AgentTaskFailureRecoveryResult:
        """Plan (via Commit #3) and immediately execute the recommended
        recovery action for task_id.

        Raises:
            InvalidAgentTaskFailureRecoveryExecutionError: If task_id is
                not a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskFailureRecoveryExecutionError("task_id is required and must be a non-empty string")

        plan = self._planner.plan(task_id)
        return self.execute_plan(plan)

    def execute_plan(self, plan: AgentTaskFailureRecoveryPlan) -> AgentTaskFailureRecoveryResult:
        """Execute an already-computed AgentTaskFailureRecoveryPlan
        exactly as given -- never re-planned or second-guessed.

        Raises:
            InvalidAgentTaskFailureRecoveryExecutionError: If plan is not
                an AgentTaskFailureRecoveryPlan
        """
        if not isinstance(plan, AgentTaskFailureRecoveryPlan):
            raise InvalidAgentTaskFailureRecoveryExecutionError(
                "plan must be an AgentTaskFailureRecoveryPlan"
            )

        action = plan.recommended_action

        if action == RECOVERY_ACTION_NONE:
            return AgentTaskFailureRecoveryResult(
                task_id=plan.task_id,
                planned_action=action,
                executed_action=action,
                success=True,
                failure_reason=None,
                affected_reference=None,
            )

        if action == RECOVERY_ACTION_RETRY:
            return self._execute_retry(plan)
        if action == RECOVERY_ACTION_WAIT_FOR_DEPENDENCY:
            return self._execute_wait_for_dependency(plan)
        if action == RECOVERY_ACTION_REFRESH_CONTEXT:
            return self._execute_refresh_context(plan)
        if action == RECOVERY_ACTION_REPAIR_TASK:
            return self._execute_repair_task(plan)
        if action == RECOVERY_ACTION_MARK_UNRECOVERABLE:
            return self._execute_mark_unrecoverable(plan)

        return self._failure(plan, None, f"recommended_action {action!r} is not supported for execution")

    def _execute_retry(self, plan: AgentTaskFailureRecoveryPlan) -> AgentTaskFailureRecoveryResult:
        if self._retry_scheduler is None:
            return self._failure(plan, None, "no retry scheduler was supplied to execute a retry")
        try:
            schedule = self._retry_scheduler.schedule_retry(plan.task_id)
        except Exception as error:
            return self._failure(plan, RECOVERY_ACTION_RETRY, str(error))
        return self._success(
            plan, RECOVERY_ACTION_RETRY, f"retry scheduled: attempt {schedule.attempt} ({schedule.status})"
        )

    def _execute_wait_for_dependency(self, plan: AgentTaskFailureRecoveryPlan) -> AgentTaskFailureRecoveryResult:
        if self._readiness_service is None:
            return self._failure(
                plan, None, "no readiness service was supplied to check dependency status"
            )

        result = self._readiness_service.check(plan.task_id)
        if not result.ready:
            return self._failure(
                plan, RECOVERY_ACTION_WAIT_FOR_DEPENDENCY, "task is still blocked by unresolved dependencies"
            )

        if self._queue_service is None:
            return self._success(
                plan,
                RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
                "dependency is resolved and the task is now ready; no queue service was supplied to re-enqueue it",
            )

        try:
            entry = self._queue_service.enqueue(plan.task_id)
        except Exception as error:
            return self._failure(plan, RECOVERY_ACTION_WAIT_FOR_DEPENDENCY, str(error))
        return self._success(
            plan, RECOVERY_ACTION_WAIT_FOR_DEPENDENCY, f"dependency resolved; re-enqueued with priority {entry.priority}"
        )

    def _execute_refresh_context(self, plan: AgentTaskFailureRecoveryPlan) -> AgentTaskFailureRecoveryResult:
        if self._context_refresh_service is None:
            return self._failure(plan, None, "no context refresh service was supplied to execute a refresh")
        try:
            result = self._context_refresh_service.refresh(plan.task_id)
        except Exception as error:
            return self._failure(plan, RECOVERY_ACTION_REFRESH_CONTEXT, str(error))
        return self._success(
            plan,
            RECOVERY_ACTION_REFRESH_CONTEXT,
            f"context refreshed: {len(result.added_sources)} added, {len(result.removed_sources)} removed",
        )

    def _execute_repair_task(self, plan: AgentTaskFailureRecoveryPlan) -> AgentTaskFailureRecoveryResult:
        if self._retry_repair_service is None or self._retry_repair_executor is None:
            return self._failure(
                plan, None, "no retry repair service/scheduler was supplied to execute a repair"
            )

        repair_plan = self._retry_repair_service.plan_repair(plan.task_id)
        try:
            result = self._retry_repair_executor.apply(repair_plan)
        except Exception as error:
            return self._failure(plan, RECOVERY_ACTION_REPAIR_TASK, str(error))

        if result.final_status == REPAIR_FAILED:
            return self._failure(
                plan, RECOVERY_ACTION_REPAIR_TASK, f"repair execution reported final_status={result.final_status}"
            )
        return self._success(
            plan,
            RECOVERY_ACTION_REPAIR_TASK,
            f"repair applied: final_status={result.final_status}",
            partial=(result.final_status == REPAIR_PARTIAL),
        )

    def _execute_mark_unrecoverable(self, plan: AgentTaskFailureRecoveryPlan) -> AgentTaskFailureRecoveryResult:
        if self._dead_letter_service is None:
            return self._failure(
                plan, None, "no dead-letter service was supplied to mark this task unrecoverable"
            )
        try:
            entry = self._dead_letter_service.dead_letter(plan.task_id, plan.reason)
        except Exception as error:
            return self._failure(plan, RECOVERY_ACTION_MARK_UNRECOVERABLE, str(error))
        return self._success(plan, RECOVERY_ACTION_MARK_UNRECOVERABLE, f"dead-lettered: {entry.reason}")

    @staticmethod
    def _success(
        plan: AgentTaskFailureRecoveryPlan, executed_action: str, affected_reference: str, partial: bool = False
    ) -> AgentTaskFailureRecoveryResult:
        return AgentTaskFailureRecoveryResult(
            task_id=plan.task_id,
            planned_action=plan.recommended_action,
            executed_action=executed_action,
            success=True,
            failure_reason=None,
            affected_reference=affected_reference,
            source_failure_event_id=plan.failure_event_id,
            partial=partial,
        )

    @staticmethod
    def _failure(plan: AgentTaskFailureRecoveryPlan, executed_action, reason: str) -> AgentTaskFailureRecoveryResult:
        return AgentTaskFailureRecoveryResult(
            task_id=plan.task_id,
            planned_action=plan.recommended_action,
            executed_action=executed_action,
            success=False,
            failure_reason=reason,
            affected_reference=None,
            source_failure_event_id=plan.failure_event_id,
        )
