from dataclasses import asdict, dataclass
from datetime import datetime

# This module's own, deliberately UPPERCASE schedule-status vocabulary
# -- the same "UPPERCASE for an outcome vocabulary distinct from
# backend.agent_task_lifecycle's own lowercase task-lifecycle states"
# split that module's own models.py already documents for backend.llm.
# tool_execution/backend.agent_capability_execution. A TaskRetrySchedule
# is not a task lifecycle state (Commit #1 already owns that) and not a
# Commit #9 RetryEligibilityResult (a stateless, recomputed-every-call
# verdict) -- it is its own small, two-state record: SCHEDULED (still
# waiting, or already due) or CANCELLED (explicitly withdrawn). There is
# deliberately no third "DUE"/"COMPLETED" status: "due" is a read-time
# query (now >= eligible_at) over a still-SCHEDULED record, never a
# separately persisted state to keep in sync (Rule: "Scheduling only;
# never execute" -- this module has no way of ever learning a retry
# actually happened, so it could never transition anything to
# "completed" truthfully), the same "compute derived state at read
# time, never persist it separately" discipline Commit #2's own
# get_reservation()/is_reservation_valid() and Commit #7's own
# find_expired() already establish for their own comparable "still
# valid as of now" questions.
SCHEDULED = "SCHEDULED"
CANCELLED = "CANCELLED"
STATUSES = frozenset({SCHEDULED, CANCELLED})


class InvalidRetryScheduleError(ValueError):
    """Raised when a TaskRetrySchedule's own fields are invalid, or
    schedule_retry()/cancel_retry()/get_retry_schedule()/
    get_due_retries() is given invalid arguments."""


@dataclass(frozen=True)
class TaskRetrySchedule(object):
    """A durable record that task_id's next retry attempt is scheduled
    to become eligible at eligible_at -- never a worker, timer, or
    scheduler that itself fires anything (Rule: "Do not invent a worker
    or scheduler"): this is data only, queried by get_due_retries(),
    never acted on by this module itself.

    Exactly one live TaskRetrySchedule exists per task_id at a time
    (the same one-current-record-per-key shape every store in this
    series already uses) -- scheduling a new attempt replaces whatever
    was there before, rather than accumulating a history of past
    schedules (Commit #... backend.agent_task_state_history already
    owns durable historical trails, for a different record entirely).

    Attributes:
        task_id: The task_id this schedule concerns.
        attempt: Which retry attempt this schedule represents -- one
            more than Commit #9's own RetryEligibilityResult.attempt_count
            at schedule_retry() time (or 1, when no attempt metadata
            was recorded for task_id at all -- this schedule is then
            the first attempt this scheduler itself is tracking).
        scheduled_at: When this schedule was created.
        eligible_at: The earliest time this attempt may actually be
            enqueued -- exactly Commit #9's own
            RetryEligibilityResult.next_eligible_at when it gave one,
            or scheduled_at itself when eligibility reported no backoff
            constraint at all (immediately eligible).
        status: SCHEDULED or CANCELLED.
        reason: Commit #9's own RetryEligibilityResult.reason, carried
            verbatim -- never a re-derived explanation of this
            scheduler's own.
    """

    task_id: str
    attempt: int
    scheduled_at: datetime
    eligible_at: datetime
    status: str
    reason: str

    def __post_init__(self):
        if not self.task_id or not isinstance(self.task_id, str):
            raise InvalidRetryScheduleError("task_id is required and must be a non-empty string")
        if not isinstance(self.attempt, int) or isinstance(self.attempt, bool) or self.attempt < 1:
            raise InvalidRetryScheduleError("attempt must be a positive int")
        if not isinstance(self.scheduled_at, datetime):
            raise InvalidRetryScheduleError("scheduled_at must be a datetime")
        if not isinstance(self.eligible_at, datetime):
            raise InvalidRetryScheduleError("eligible_at must be a datetime")
        if self.status not in STATUSES:
            raise InvalidRetryScheduleError(f"status {self.status!r} is not one of {sorted(STATUSES)}")
        if not self.reason or not isinstance(self.reason, str):
            raise InvalidRetryScheduleError("reason is required and must be a non-empty string")

    def to_dict(self) -> dict:
        data = asdict(self)
        data["scheduled_at"] = self.scheduled_at.isoformat()
        data["eligible_at"] = self.eligible_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "TaskRetrySchedule":
        payload = dict(data)
        for key in ("scheduled_at", "eligible_at"):
            value = payload.get(key)
            if isinstance(value, str):
                payload[key] = datetime.fromisoformat(value)
        return cls(**payload)
