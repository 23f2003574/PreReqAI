from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional


class InvalidQueueEntryError(ValueError):
    """Raised when a QueueEntry's own fields are invalid, or enqueue()/
    peek()/claim() is given invalid arguments."""


@dataclass(frozen=True)
class QueueEntry(object):
    """One task_id's record of being queued for ready work -- queue
    membership and claim ownership only, never a second lifecycle
    record: backend.agent_task_lifecycle.AgentTask already owns whether
    task_id itself is CREATED/PLANNED/READY/.../COMPLETED, and this
    entry's own presence or absence in a store never feeds back into
    that state (Rule: "Queue state is not task lifecycle state").

    Modeled on backend.agent_policy_risk_review_queue.ReviewItem's own
    immutable, dataclasses.replace()-not-mutate shape: claim() never
    mutates an entry in place, it replaces it with a new QueueEntry
    carrying claimant_id/claimed_at set.

    Attributes:
        task_id: The backend.agent_task_lifecycle.AgentTask.task_id this
            entry queues. Exactly one live QueueEntry exists per
            task_id at a time (a store keys entries by task_id, the
            same one-current-record-per-id shape
            backend.agent_task_readiness_projection.
            AgentTaskReadinessProjection already uses).
        priority: Higher runs first -- the same "higher first" numeric
            convention backend.llm.context.LLMContextItem.priority
            already establishes (int, default 0) for this repository's
            only other explicit priority field.
        queued_at: When this task_id was first enqueued. Never changes
            on a repeated enqueue() of the same task_id (Rule:
            "Repeated enqueue follows existing idempotency
            conventions") or on claim() (claiming does not re-queue).
        claimant_id: Who currently owns this entry -- None until
            claim()ed.
        claimed_at: When claimant_id claimed this entry, or None if it
            never was. Set together with claimant_id, never one without
            the other.
    """

    task_id: str
    priority: int = 0
    queued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    claimant_id: Optional[str] = None
    claimed_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.task_id or not isinstance(self.task_id, str):
            raise InvalidQueueEntryError("task_id is required and must be a non-empty string")
        if not isinstance(self.priority, int):
            raise InvalidQueueEntryError("priority must be an int")
        if (self.claimant_id is None) != (self.claimed_at is None):
            raise InvalidQueueEntryError("claimant_id and claimed_at must be set together")
        if self.claimant_id is not None and (not isinstance(self.claimant_id, str) or not self.claimant_id.strip()):
            raise InvalidQueueEntryError("claimant_id must be a non-empty string when given")

    def to_dict(self) -> dict:
        data = asdict(self)
        data["queued_at"] = self.queued_at.isoformat()
        data["claimed_at"] = self.claimed_at.isoformat() if self.claimed_at is not None else None
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "QueueEntry":
        payload = dict(data)
        value = payload.get("queued_at")
        if isinstance(value, str):
            payload["queued_at"] = datetime.fromisoformat(value)
        claimed_at = payload.get("claimed_at")
        if isinstance(claimed_at, str):
            payload["claimed_at"] = datetime.fromisoformat(claimed_at)
        return cls(**payload)
