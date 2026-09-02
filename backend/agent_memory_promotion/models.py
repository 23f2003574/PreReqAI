from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# Plain string status vocabulary, the same convention
# backend.llm.tool_execution's SUCCEEDED/FAILED and
# backend.llm.evaluation_gates's ACCEPTED/REJECTED already use, rather
# than a new Enum type.
CANDIDATE = "candidate"
TRUSTED = "trusted"
DEPRECATED = "deprecated"
STATUSES = frozenset({CANDIDATE, TRUSTED, DEPRECATED})

# On the same [0.0, 1.0] scale backend.llm.evaluation_scoring and Commit
# #6's LLMAgentMemoryQuality already use. Both thresholds must be met --
# a memory with a strong quality_score but thin evidence still cannot
# become trusted (see LLMAgentMemoryQuality.confidence's own docstring on
# why the two are kept separate).
MIN_TRUSTED_QUALITY = 0.7
MIN_TRUSTED_CONFIDENCE = 0.7


@dataclass(frozen=True)
class LLMAgentMemoryPromotionRecord:
    """One lifecycle decision for a Commit #1 memory: candidate, trusted, or deprecated.

    Never updated or deleted once recorded -- promote()/deprecate() only
    ever append a new record, the same append-only history convention
    Commit #5's LLMAgentMemoryFeedback already establishes, so a memory's
    full promotion/deprecation history stays reachable rather than being
    collapsed to a single mutable field. The memory itself (its content,
    execution_id, outcome, created_at) is never touched by any of this --
    a status change is recorded here, alongside it, never inside it.

    quality_score/confidence are the Commit #6 assessment this decision
    was based on, captured at decided_at -- provenance for *why* the
    decision was made, not merely *that* it was.
    """

    memory_id: str
    status: str
    reason: str
    quality_score: float
    confidence: float
    promotion_id: str = field(default_factory=lambda: str(uuid4()))
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["decided_at"] = self.decided_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentMemoryPromotionRecord":
        payload = dict(data)
        value = payload.get("decided_at")
        if isinstance(value, str):
            payload["decided_at"] = datetime.fromisoformat(value)
        return cls(**payload)


@dataclass(frozen=True)
class LLMAgentMemoryPromotionDecision:
    """What evaluate() recommends for a memory right now, and why -- a
    preview: computing this never appends a LLMAgentMemoryPromotionRecord
    or changes the memory's current status. promote() calls evaluate()
    internally and only proceeds when eligible is True.
    """

    memory_id: str
    current_status: str
    recommended_status: str
    eligible: bool
    reason: str
    quality_score: float
    confidence: float
    evaluated_at: datetime
