from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class RetryEligibilityResult(object):
    """LLMAgentTaskQueueRetryEligibilityService.check()'s complete,
    read-only verdict for one task_id -- never itself enqueues,
    retries, or dead-letters anything (Rule: "Read-only; do not enqueue
    or retry the task"): this is purely a report.

    Attributes:
        task_id: The task_id this result concerns.
        eligible: Whether task_id may currently return to normal queue
            processing -- exactly `not blocked by any evaluated rule`.
        reason: A single, human-readable explanation -- the first
            blocking rule found (see the service's own docstring for
            check order), or a positive confirmation when eligible.
        attempt_count: How many attempts this task has already used,
            or None if no attempt/retry metadata is recorded for it at
            all (Rule: "Missing retry metadata must produce an
            explicit result, not an invented default" -- None, never a
            fabricated 0).
        remaining_attempts: max_attempts - attempt_count, floored at 0,
            or None under the same "no metadata recorded" condition as
            attempt_count.
        next_eligible_at: The earliest time this task's own backoff
            window permits another attempt, or None if no backoff
            metadata applies at all (never attempted, or no policy/
            explicit timestamp recorded).
        dead_letter_required: True when this task's retry attempts are
            exhausted and it is not already dead-lettered -- an
            advisory signal only (Rule: this service never calls
            backend.agent_task_queue_dead_letter.
            LLMAgentTaskDeadLetterService.dead_letter() itself; a
            caller decides what, if anything, to do with this flag).
    """

    task_id: str
    eligible: bool
    reason: str
    attempt_count: Optional[int] = None
    remaining_attempts: Optional[int] = None
    next_eligible_at: Optional[datetime] = None
    dead_letter_required: bool = False
