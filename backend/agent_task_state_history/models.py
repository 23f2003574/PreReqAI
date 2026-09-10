from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# Moved here from Commit #1's own backend.agent_task_lifecycle, where it
# started out embedded directly in LLMAgentTaskLifecycleService itself.
# This goal's own Rule ("make it possible to inspect exactly how a task
# reached its current state without putting history logic inside the
# lifecycle service itself") retroactively corrects that: a Commit #1
# transition is now recorded from the outside, by
# LLMAgentTaskStateHistoryService (via .tracked's
# LLMAgentTaskLifecycleHistoryTrackedService), the same "the entity
# service never records its own history; a separate service does, called
# from a thin wrapper" split backend.agent_policy_history/backend.
# agent_policy_history.tracked already establish for
# backend.agent_policy_engine. Commit #1 itself is otherwise unchanged:
# same fields (task_id, from_state, to_state, reason, occurred_at), same
# shape, same serialization -- only where it lives, and who writes it,
# has moved.


@dataclass(frozen=True)
class TaskTransitionRecord:
    """One immutable, append-only entry in a Commit #1 AgentTask's own
    transition history.

    from_state is None only for the very first entry a task ever gets
    (its creation, to_state=backend.agent_task_lifecycle.CREATED) -- the
    same "before/from is None only for the creation event" convention
    backend.agent_policy_history.LLMAgentPolicyChange already
    establishes. Never updated or deleted once recorded -- the same
    append-only discipline backend.agent_strategy_lifecycle.
    LLMAgentStrategyLifecycleDecision and backend.agent_policy_history.
    LLMAgentPolicyChange already establish elsewhere in this repository.
    """

    task_id: str
    from_state: Optional[str]
    to_state: str
    reason: Optional[str] = None
    transition_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["occurred_at"] = self.occurred_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "TaskTransitionRecord":
        payload = dict(data)
        value = payload.get("occurred_at")
        if isinstance(value, str):
            payload["occurred_at"] = datetime.fromisoformat(value)
        return cls(**payload)
