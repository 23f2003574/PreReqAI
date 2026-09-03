from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LLMAgentStrategyScore:
    """One deterministic, point-in-time judgment of a Commit #1 strategy's
    effectiveness, from the Commit #3 outcome evidence available when it
    was scored.

    score and confidence are both normalized to [0.0, 1.0], the same
    quality_score/confidence split
    backend.agent_memory_quality_assessment.LLMAgentMemoryQuality already
    uses for memories, applied here to strategy outcome history instead:
    score is what the evidence says about the strategy (recency-weighted
    effectiveness), confidence is how much that evidence is worth
    trusting (how much of it there is, and whether it agrees with
    itself). A strategy backed by one lone success and a strategy backed
    by ten consistent ones can share the same score while having very
    different confidence -- score() never lets one execution alone earn
    high confidence, whatever score it produces.

    evidence_count/succeeded_count/failed_count are the raw Commit #3
    outcome tallies this judgment was computed from -- provenance for
    what evidence existed, not merely a summary of the result.
    reason is a human-readable breakdown of how score/confidence
    combined, the same explainability convention
    backend.agent_memory_relevance_scoring.ScoredMemory.reason and
    LLMAgentMemoryQuality.assessment_reason already establish. scored_at
    is when this particular judgment was made -- scoring the same
    strategy_id again later, as more outcomes accumulate or simply as
    existing ones age, can produce a different result: this is a
    snapshot, never a permanent verdict, and is never itself stored.
    """

    strategy_id: str
    score: float
    confidence: float
    evidence_count: int
    succeeded_count: int
    failed_count: int
    reason: str
    scored_at: datetime
