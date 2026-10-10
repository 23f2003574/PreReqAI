from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class RetryReconciliationResult(object):
    """LLMAgentTaskRetryReconciliationService.reconcile()'s complete,
    read-only report -- never itself enqueues, retries, cancels, or
    mutates a schedule (Rule: "Read-only analysis; do not enqueue,
    retry, cancel, or mutate schedules"): every list here is a finding,
    never an action already taken.

    valid_schedules/due_schedules/stale_schedules/invalid_schedules
    hold the actual backend.agent_task_queue_retry_scheduler.
    TaskRetrySchedule records found in each state -- missing_schedules
    holds bare task_id strings instead, since by definition there is no
    schedule record to reference (Rule: "Identify tasks that should
    have a retry schedule but do not").

    Attributes:
        task_id: The task_id reconcile() was scoped to, or None for a
            full sweep over every currently persisted schedule.
        valid_schedules: Schedules that still correctly reflect current
            task/eligibility state and are not yet due.
        due_schedules: Schedules that still correctly reflect current
            state, and whose own eligible_at has passed (Behavior:
            "Detect ... due" schedules).
        stale_schedules: Schedules whose own attempt no longer matches
            what a fresh eligibility check would expect -- task_id
            failed (or was otherwise re-attempted) again since this
            schedule was made, so it is superseded, not wrong about
            whether task_id can ever retry again.
        invalid_schedules: Schedules for a task_id that is no longer a
            legitimate retry candidate at all: it no longer exists,
            it is dead-lettered, it has reached a terminal COMPLETED
            state, or Commit #9's own eligibility check now reports
            ineligible for a reason other than backoff timing (Rule:
            "Treat dead-lettered/completed tasks as invalid retry
            candidates").
        missing_schedules: task_ids (only ever populated when
            reconcile() was scoped to one specific task_id -- see that
            method's own docstring for why a full sweep cannot
            enumerate this) that are currently eligible for retry but
            have no live (SCHEDULED) schedule at all.
        actions_required: Human-readable, advisory descriptions of the
            corrective action each non-valid/non-due finding above
            implies -- described, never performed (Behavior: "Report
            required corrective actions without performing them").
    """

    task_id: Optional[str] = None
    valid_schedules: list = field(default_factory=list)
    due_schedules: list = field(default_factory=list)
    stale_schedules: list = field(default_factory=list)
    invalid_schedules: list = field(default_factory=list)
    missing_schedules: list = field(default_factory=list)
    actions_required: list = field(default_factory=list)
