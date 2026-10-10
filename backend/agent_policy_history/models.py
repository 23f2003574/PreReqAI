from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# The kinds of meaningful change this trail records. Deliberately small
# and closed, the same reasoning every other closed vocabulary in this
# series (STATUSES, EFFECTS, ...) already documents. Two Commit #1
# lifecycle events (CREATED/UPDATED/ARCHIVED) and two Commit #5 exception
# events (EXCEPTION_CREATED/EXCEPTION_REVOKED) -- a change always
# belongs to exactly one of these, never inferred from before/after
# alone.
CREATED = "created"
UPDATED = "updated"
ARCHIVED = "archived"
EXCEPTION_CREATED = "exception_created"
EXCEPTION_REVOKED = "exception_revoked"
CHANGE_TYPES = frozenset({CREATED, UPDATED, ARCHIVED, EXCEPTION_CREATED, EXCEPTION_REVOKED})


@dataclass(frozen=True)
class LLMAgentPolicyChange:
    """One immutable, append-only snapshot of a meaningful change to a
    Commit #1 policy or one of its Commit #5 exceptions.

    before/after are full, JSON-safe snapshots (LLMAgentPolicy.to_dict()/
    LLMAgentPolicyException.to_dict(), with any secret-looking string
    value redacted) of the entity immediately before and immediately
    after this change -- never a field-level diff. This is what lets
    LLMAgentPolicyHistoryService.get_at() reconstruct "the applicable
    version" for any timestamp deterministically: it is simply the
    `after` snapshot of the latest change at or before that timestamp,
    nothing needs to be replayed or recomputed from a sequence of edits.
    before is None only for a CREATED or EXCEPTION_CREATED change, since
    nothing existed beforehand.

    Never updated or deleted once recorded -- LLMAgentPolicyHistoryService.
    record_change() only ever appends a new LLMAgentPolicyChange, the
    same append-only discipline
    backend.agent_strategy_lifecycle.LLMAgentStrategyLifecycleDecision and
    backend.agent_strategy_decision_audit.LLMAgentStrategyDecision already
    establish elsewhere in this repository. Recording a change never
    mutates the policy or exception it observes.

    Attributes:
        scope_id: The scope this change happened within. A change is
            never consulted for, or leaks into, any other scope
        policy_id: The Commit #1 policy this change is about -- for an
            exception change, the policy_id the exception itself excepts
        change_type: One of CHANGE_TYPES
        before: The entity's full snapshot immediately before this
            change, or None if nothing existed yet
        after: The entity's full snapshot immediately after this change
        actor: Who or what made the change, when known (a subject
            identifier, a service name, ...); None when not supplied
        reason: Why the change was made, when the caller supplied one
            (e.g. Commit #12's own rollback records why it rolled back);
            None when not supplied. Added alongside Commit #12 as a
            purely additive field -- every change recorded before it
            existed simply has reason=None, exactly as if it had always
            been there
    """

    scope_id: str
    policy_id: str
    change_type: str
    before: Optional[dict]
    after: Optional[dict]
    actor: Optional[str] = None
    reason: Optional[str] = None
    change_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentPolicyChange":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)
