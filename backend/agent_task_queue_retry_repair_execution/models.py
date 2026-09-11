from dataclasses import dataclass, field

# This module's own outcome vocabulary for one apply() call as a whole
# -- deliberately distinct from backend.agent_task_queue_retry_repair's
# own per-operation UPDATE/CANCEL/CREATE/BLOCKED vocabulary (a plan's
# own operation *kinds*, not an execution *outcome*), the same
# UPPERCASE-for-an-outcome-vocabulary split backend.agent_task_lifecycle's
# own models.py already documents.
SUCCESS = "SUCCESS"
PARTIAL = "PARTIAL"
FAILED = "FAILED"
NO_OP = "NO_OP"
FINAL_STATUSES = frozenset({SUCCESS, PARTIAL, FAILED, NO_OP})


class InvalidRetryRepairPlanError(ValueError):
    """Raised when apply() is given something other than a
    backend.agent_task_queue_retry_repair.RetryRepairPlan."""


@dataclass(frozen=True)
class RetryRepairResult(object):
    """LLMAgentTaskRetryRepairExecutor.apply()'s complete report of one
    repair plan's own execution -- every operation the plan named is
    accounted for in exactly one of these three lists (Rule: "No silent
    mutations"; Behavior 6: "Report partial failures without hiding
    successful operations").

    Attributes:
        applied_operations: backend.agent_task_queue_retry_repair.
            RepairOperation entries that were actually executed
            (through Commit #10's own scheduler, successfully -- this
            includes an operation that turned out to be a no-op because
            it was already applied; see this class's own idempotency
            discussion in LLMAgentTaskRetryRepairExecutor's docstring).
        skipped_operations: RepairOperation entries this call
            deliberately never attempted -- concretely, every BLOCKED
            entry in the plan (Rule: "Only execute operations
            explicitly present in the repair plan" -- a BLOCKED entry
            names a discrepancy, never an operation to perform).
        failed_operations: (RepairOperation, error) pairs for anything
            this call attempted and could not complete -- most notably
            a CREATE operation whose task_id is no longer eligible as
            of right now (Behavior 2/3: "Re-check retry eligibility
            for operations that create schedules" -- rejected via
            Commit #10's own IneligibleForRetryError, never silently
            dropped).
        final_status: SUCCESS (something was applied, nothing failed --
            including a plan re-applied with nothing changed since:
            each operation's own idempotent re-run still counts as
            applied, never as skipped), PARTIAL (some applied, some
            failed), FAILED (something was attempted, all of it
            failed), or NO_OP (the plan named no update/cancel/create
            operations to attempt at all -- e.g. every entry was
            BLOCKED, or the plan was entirely empty).
    """

    applied_operations: list = field(default_factory=list)
    skipped_operations: list = field(default_factory=list)
    failed_operations: list = field(default_factory=list)
    final_status: str = NO_OP
