from backend.agent_task_queue import InvalidQueueEntryError
from backend.agent_task_queue_retry_repair import CANCEL, CREATE, UPDATE, RetryRepairPlan
from backend.agent_task_queue_retry_scheduler import IneligibleForRetryError, LLMAgentTaskRetryScheduler

from .models import FAILED, NO_OP, PARTIAL, SUCCESS, InvalidRetryRepairPlanError, RetryRepairResult


class LLMAgentTaskRetryRepairExecutor:
    """Applies exactly the operations a Commit #12
    backend.agent_task_queue_retry_repair.RetryRepairPlan already named
    -- never a second retry engine or scheduler (Rule: "Do not create
    another retry engine or scheduler"): apply() never decides *what*
    should change (that is entirely Commit #11's reconcile() and
    Commit #12's own plan_repair() own job, already done by the time a
    plan reaches here), it only carries out what the plan already
    proposed, through Commit #10's own scheduler (Rule: "Only execute
    operations explicitly present in the repair plan").

    Every kind of operation maps onto exactly one existing Commit #10
    call, never a new mutation path of its own (Behavior 3: "Apply
    cancellations/updates/creations through existing scheduling APIs"):
      - UPDATE and CREATE both call scheduler.schedule_retry(task_id).
        For CREATE this is exactly what "revalidate then create" means
        (Behavior 2: "Re-check retry eligibility for operations that
        create schedules") -- schedule_retry() itself always resolves
        eligibility fresh, at the real *current* time (this class
        passes no `now` of its own; apply() may run at any point after
        the plan was made), and raises Commit #10's own
        IneligibleForRetryError if task_id is no longer eligible,
        rather than this class duplicating that check. For UPDATE, the
        exact same call is also the correct fix: schedule_retry()
        always recomputes attempt/eligible_at from current state and
        saves that in place of whatever was stored before (Commit #10's
        own save()-by-task_id shape), so a schedule whose own attempt
        had drifted is corrected as a side effect of the identical call
        a CREATE uses -- there is no separate "update in place" API to
        invent (Rule: "Reuse existing services").
      - CANCEL calls scheduler.cancel_retry(task_id).
      - BLOCKED entries are never executed at all -- they are not
        operations, they are Commit #12's own explicit refusal to
        propose one (Rule: "Never bypass dead-letter, lifecycle, or
        retry policies" -- silently resolving a BLOCKED entry here
        would be exactly that). Every one is reported in
        skipped_operations, not silently dropped.

    Every attempted operation runs independently, and every one is
    attempted regardless of whether an earlier one in the same call
    failed (Behavior 6: "Report partial failures without hiding
    successful operations"; Rule: "A failed repair must not corrupt an
    otherwise valid schedule" -- a failure never rolls back, or even
    touches, any other operation's own already-applied result, since
    each is a wholly separate schedule_retry()/cancel_retry() call
    against its own task_id). The whole call runs under Commit #10's
    own scheduler.atomic() (Rule: "Reuse existing persistence/
    transaction mechanisms") purely for mutual exclusion against other
    threads mutating the same schedules mid-apply -- never a rollback
    mechanism; there isn't one to reuse (this repository's own stores
    have none -- see Commit #5's own BatchOperationError docstring for
    the same conclusion reached there).

    Idempotent (Behavior 5: "Make each operation idempotent"): every
    operation this class performs is exactly one of Commit #10's own
    already-idempotent schedule_retry()/cancel_retry() calls, so
    applying the identical plan twice in a row produces the identical
    end state both times -- the second call's own operations still
    land in applied_operations (they still ran, and still succeeded;
    see RetryRepairResult's own docstring for why that is not the same
    as "skipped").

    Never touches valid schedules (Rule/Behavior 4: "Preserve valid
    schedules"): a plan never names an operation for a task_id Commit
    #12 found valid or due in the first place (see RetryRepairPlan's
    own docstring), so there is structurally nothing for apply() to do
    to one -- this class does not need its own logic to "leave valid
    schedules alone," it simply never sees them as operations at all.

    Never executes the underlying agent task (Rule): nothing here ever
    calls backend.agent_task_queue.LLMAgentTaskQueueService.enqueue()
    or anything execution-related at all.
    """

    def __init__(self, scheduler: LLMAgentTaskRetryScheduler):
        """
        Args:
            scheduler: The exact Commit #10 LLMAgentTaskRetryScheduler
                instance the plan being applied was itself built
                against -- required, never defaulted.
        """
        self._scheduler = scheduler

    def apply(self, plan: RetryRepairPlan) -> RetryRepairResult:
        """Apply plan's own schedule_updates/schedules_to_cancel/
        schedules_to_create, skip its own blocked_repairs entirely, and
        report exactly what happened (Behavior 1: "Validate the repair
        plan before applying it").

        Raises:
            InvalidRetryRepairPlanError: If plan is not a
                backend.agent_task_queue_retry_repair.RetryRepairPlan
        """
        if not isinstance(plan, RetryRepairPlan):
            raise InvalidRetryRepairPlanError(
                f"plan must be a RetryRepairPlan, got {type(plan).__name__}"
            )

        applied, failed = [], []

        with self._scheduler.atomic():
            for operation in plan.schedule_updates:
                self._apply_one(operation, applied, failed)
            for operation in plan.schedules_to_cancel:
                self._apply_one(operation, applied, failed)
            for operation in plan.schedules_to_create:
                self._apply_one(operation, applied, failed)

        skipped = list(plan.blocked_repairs)

        return RetryRepairResult(
            applied_operations=applied,
            skipped_operations=skipped,
            failed_operations=failed,
            final_status=self._final_status(applied, failed),
        )

    def _apply_one(self, operation, applied: list, failed: list) -> None:
        try:
            if operation.operation in (UPDATE, CREATE):
                self._scheduler.schedule_retry(operation.task_id)
            elif operation.operation == CANCEL:
                self._scheduler.cancel_retry(operation.task_id)
            applied.append(operation)
        except (IneligibleForRetryError, InvalidQueueEntryError) as error:
            failed.append((operation, error))

    @staticmethod
    def _final_status(applied: list, failed: list) -> str:
        if not applied and not failed:
            return NO_OP
        if failed and not applied:
            return FAILED
        if failed and applied:
            return PARTIAL
        return SUCCESS
