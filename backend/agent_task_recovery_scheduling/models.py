from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

# Fresh, same-shape reimplementation of backend.agent_task_queue_retry_scheduler's
# own SCHEDULED/CANCELLED vocabulary (this project's own established
# convention for reusing a lifecycle vocabulary across a different
# identity space -- a preflight schedule is keyed by (task_id,
# preflight_id), never just task_id), extended with INVALIDATED: a purely
# computed, never-persisted status a still-SCHEDULED record can read as
# once its own authorization is no longer valid (Commit #10's own
# validate()), the same "compute effective status fresh on every read,
# never mutate the stored record" discipline
# backend.agent_policy_risk_approval.LLMAgentRiskApprovalGate._effective()
# already establishes.
SCHEDULED = "scheduled"
CANCELLED = "cancelled"
INVALIDATED = "invalidated"
SCHEDULE_STATUSES = frozenset({SCHEDULED, CANCELLED, INVALIDATED})


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightSchedule:
    """Immutable record that one EXACT, approved, currently-authorized
    Commit #4(-of-agent_task_recovery_guardrails) preflight has been
    scheduled for a later execution window -- never itself an execution
    (Rule: "Do not execute recovery; this commit only manages scheduling
    state"). Bound to the exact (task_id, preflight_id) (Rule: "Bind the
    schedule to the exact task_id + preflight_id"), never any other
    preflight_id for the same task.

    authorization_id references the exact Commit #9 authorization
    schedule() itself created/reused while validating that this preflight
    could be scheduled at all -- a reference, never a copy of its own
    fields, and the same authorization re-validated live (via Commit
    #10's own validate()) whenever this schedule's effective status is
    read.

    execute_at is the caller's own requested execution window, or None
    for "as soon as an eligible window allows" -- this commit never
    interprets or acts on it (Rule: "without executing it immediately");
    a later, separate commit's own consumer is what would actually read
    and act on it.

    status is SCHEDULED or CANCELLED as actually stored (never
    INVALIDATED as a persisted value -- that is only ever a computed,
    read-time view, see models.py's own module docstring above).
    """

    task_id: str
    preflight_id: str
    authorization_id: str
    execute_at: Optional[datetime]
    status: str
    created_at: datetime
    cancelled_at: Optional[datetime]
    cancellation_reason: Optional[str]
    schedule_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["execute_at"] = self.execute_at.isoformat() if self.execute_at else None
        data["created_at"] = self.created_at.isoformat()
        data["cancelled_at"] = self.cancelled_at.isoformat() if self.cancelled_at else None
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryPreflightSchedule":
        payload = dict(data)
        for key in ("execute_at", "created_at", "cancelled_at"):
            value = payload.get(key)
            if isinstance(value, str):
                payload[key] = datetime.fromisoformat(value)
        return cls(**payload)
