from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


class InvalidReservationError(ValueError):
    """Raised when a QueueReservation's own fields are invalid or
    inconsistent, or reserve() is given invalid arguments."""


@dataclass(frozen=True)
class QueueReservation(object):
    """One claimant's time-bound ownership window over a Commit #1
    QueueEntry -- a controlled lease, not a second queue record (Rule:
    "do not duplicate queue entries"): this reservation only ever
    exists alongside a live Commit #1 QueueEntry whose own claimant_id
    LLMAgentTaskQueueReservationService keeps in lock-step with this
    record's own claimant_id via that service's claim()/release(); the
    two are never independently true.

    Unlike Commit #1's own QueueEntry (which has no notion of time-
    bound ownership at all -- a claim() there lasts until an explicit
    release()/remove()), expires_at is always a concrete deadline, never
    None: Goal's own "a controlled ownership window" means every
    reservation is bounded, the same "explicit expiration window,
    always set" discipline
    backend.agent_policy_risk_approval.ApprovalRequirement's own
    REQUIRED-state expires_at and backend.agent_policy_risk_escalation.
    Escalation's own PENDING-state expires_at already establish for a
    comparable time-bound record elsewhere in this repository (this one
    simply never has an unbounded state to begin with, since a
    reservation with no ownership window at all would not be "a
    controlled ownership window" per this commit's own goal).

    Modeled on those same records' own immutable, dataclasses.replace()
    -not-mutate shape -- there is no in-place mutation method here at
    all: LLMAgentTaskQueueReservationService always saves a whole new
    QueueReservation (a fresh reserve()) or deletes this one outright
    (release()/expire_stale_reservations()), never edits one in place.

    Attributes:
        task_id: The backend.agent_task_queue.QueueEntry.task_id this
            reservation covers. Exactly one live QueueReservation
            exists per task_id at a time.
        claimant_id: Who currently owns this reservation -- exactly the
            same identifier passed as claimant_id to the underlying
            Commit #1 QueueEntry's own claim().
        expires_at: The deadline after which this reservation is no
            longer valid (Rule: "Expired reservations become claimable
            again") -- always a datetime, never None.
        reserved_at: When this reservation was created.
    """

    task_id: str
    claimant_id: str
    expires_at: datetime
    reserved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.task_id or not isinstance(self.task_id, str):
            raise InvalidReservationError("task_id is required and must be a non-empty string")
        if not self.claimant_id or not isinstance(self.claimant_id, str):
            raise InvalidReservationError("claimant_id is required and must be a non-empty string")
        if not isinstance(self.expires_at, datetime):
            raise InvalidReservationError("expires_at is required and must be a datetime")
        if not isinstance(self.reserved_at, datetime):
            raise InvalidReservationError("reserved_at must be a datetime")

    def to_dict(self) -> dict:
        data = asdict(self)
        data["reserved_at"] = self.reserved_at.isoformat()
        data["expires_at"] = self.expires_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "QueueReservation":
        payload = dict(data)
        for key in ("reserved_at", "expires_at"):
            value = payload.get(key)
            if isinstance(value, str):
                payload[key] = datetime.fromisoformat(value)
        return cls(**payload)
