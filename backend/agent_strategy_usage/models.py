from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

# selection_score is Commit #5's own bounded combined_score (relevance and
# effectiveness are each already in [0.0, 1.0], and its weights sum to
# 1.0), carried through unchanged as provenance -- never re-derived here.
MIN_SELECTION_SCORE = 0.0
MAX_SELECTION_SCORE = 1.0


@dataclass(frozen=True)
class LLMAgentStrategyUsage:
    """One explicit record that a Commit #1 strategy was selected -- and,
    separately, whether it was actually applied -- for a real execution.

    Links every usage to both strategy_id and execution_id, always --
    neither is ever optional, the same provenance discipline Commit #3's
    LLMAgentStrategyOutcome already applies. selection_score is the
    Commit #5 combined_score this strategy was selected with, carried
    through as selection provenance rather than recomputed from scratch
    later. applied distinguishes a strategy Commit #5 merely selected as a
    candidate from one that actually reached Commit #6's applied planning
    context -- the two are never conflated into a single "used" flag.

    Never updated or deleted once recorded -- record() only ever appends
    a new LLMAgentStrategyUsage (or, for a (strategy_id, execution_id)
    pair already on record, returns the existing one unchanged), the same
    append-only, idempotent-by-pair discipline
    backend.agent_strategy_effectiveness.LLMAgentStrategyOutcome already
    establishes for outcome evidence.

    Recording usage never judges or scores effectiveness itself -- that
    stays entirely Commit #3/#4's job; a usage record is raw evidence a
    later commit (Commit #8) can consume, not a verdict this module forms
    on its own.
    """

    strategy_id: str
    execution_id: str
    selection_score: float
    applied: bool
    usage_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentStrategyUsage":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)
