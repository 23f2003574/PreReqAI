from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# The kinds of judgment feedback can express about how a Commit #1 memory
# performed when it was consulted for a (possibly later) execution.
# Deliberately small and closed, the same reasoning
# backend.agent_execution_memory.VALID_MEMORY_TYPES documents.
VALID_FEEDBACK_TYPES = frozenset(
    {
        "useful",
        "not_useful",
        "incorrect",
        "successful",
        "failed",
    }
)

# rating is an optional intensity alongside feedback_type's category --
# bounded so no single piece of feedback can claim more weight than a
# maximally positive or negative judgment.
MIN_RATING = -1.0
MAX_RATING = 1.0


@dataclass
class LLMAgentMemoryFeedback:
    """One explicit judgment about how a Commit #1 memory performed.

    This is feedback about a memory, not a verified fact the way
    LLMAgentMemory.outcome is: outcome is only ever derived from a
    LLMAgentPlanExecutionService record (Commit #1's own verification
    discipline), but feedback_type/rating/comment here are exactly what a
    caller reports -- an input for later learning, never treated as
    ground truth by this service itself. execution_id still names a real,
    existing execution (verified by LLMAgentMemoryFeedbackService.record()),
    but it need not be the same execution that produced memory_id: it is
    whichever execution the memory was consulted for when this feedback
    was formed, so the same memory can accumulate feedback from many
    later reuses over time.

    Never updated or deleted once recorded -- record() only ever appends
    a new LLMAgentMemoryFeedback, preserving the full feedback history for
    a memory rather than overwriting an earlier judgment with a later one.
    """

    memory_id: str
    execution_id: str
    feedback_type: str
    rating: Optional[float] = None
    comment: str = ""
    feedback_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentMemoryFeedback":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)
