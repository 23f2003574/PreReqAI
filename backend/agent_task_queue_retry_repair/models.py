from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

UPDATE = "update"
CANCEL = "cancel"
CREATE = "create"
BLOCKED = "blocked"
OPERATIONS = frozenset({UPDATE, CANCEL, CREATE, BLOCKED})


class InvalidRepairOperationError(ValueError):
    """Raised when a RepairOperation's own fields are invalid."""


@dataclass(frozen=True)
class RepairOperation(object):
    """One proposed, not-yet-applied correction -- never performed by
    this module itself (Rule: "Planning only -- no mutation"; Behavior
    6: "operations that can later be applied by a separate command/
    service"). Every operation names task_id, which kind it is
    (UPDATE/CANCEL/CREATE/BLOCKED), and why (Rule: "Every proposed
    operation must include its reason") -- never silent (Rule: "Never
    silently repair inconsistencies").

    proposed_attempt/proposed_eligible_at are only ever set for UPDATE
    (correct an existing schedule's own attempt/eligible_at in place)
    and CREATE (the attempt/eligible_at a fresh schedule would carry) --
    both read verbatim from a fresh Commit #9/#10 eligibility
    resolution (Rule: "Revalidate retry eligibility before proposing a
    new schedule"), never computed by this module's own formula. CANCEL
    and BLOCKED never propose a schedule shape at all -- a CANCEL is
    simply "this schedule should no longer exist," and a BLOCKED entry
    is exactly "this service could not safely determine what schedule,
    if any, should exist" (Rule: "If a repair cannot be safely
    determined, report it as blocked").
    """

    task_id: str
    operation: str
    reason: str
    proposed_attempt: Optional[int] = None
    proposed_eligible_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.task_id or not isinstance(self.task_id, str):
            raise InvalidRepairOperationError("task_id is required and must be a non-empty string")
        if self.operation not in OPERATIONS:
            raise InvalidRepairOperationError(f"operation {self.operation!r} is not one of {sorted(OPERATIONS)}")
        if not self.reason or not isinstance(self.reason, str):
            raise InvalidRepairOperationError("reason is required and must be a non-empty string")


@dataclass(frozen=True)
class RetryRepairPlan(object):
    """LLMAgentTaskRetryRepairService.plan_repair()'s complete,
    read-only plan -- a report of what *should* change, never a change
    itself (Rule: "Planning only -- no mutation").

    Attributes:
        tasks: Every task_id this plan actually considered, sorted --
            including ones needing no operation at all (Behavior 5:
            "Preserve valid schedules unchanged" still means that
            task_id was looked at).
        schedule_updates: RepairOperations of kind UPDATE -- an
            existing schedule whose own attempt/eligible_at should be
            corrected in place, task_id itself still being a valid,
            eligible retry candidate.
        schedules_to_cancel: RepairOperations of kind CANCEL -- an
            existing schedule that should be withdrawn outright, with
            no replacement proposed (task_id is no longer a valid
            retry candidate at all).
        schedules_to_create: RepairOperations of kind CREATE -- a
            task_id that is currently eligible for retry but has no
            live schedule.
        blocked_repairs: RepairOperations of kind BLOCKED -- a
            discrepancy this service will not silently resolve on its
            own (see RepairOperation's own docstring).
        summary: A short, deterministic human-readable count of the
            above.
    """

    tasks: list = field(default_factory=list)
    schedule_updates: list = field(default_factory=list)
    schedules_to_cancel: list = field(default_factory=list)
    schedules_to_create: list = field(default_factory=list)
    blocked_repairs: list = field(default_factory=list)
    summary: str = ""
