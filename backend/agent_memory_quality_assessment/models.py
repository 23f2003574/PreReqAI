from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LLMAgentMemoryQuality:
    """One deterministic, point-in-time judgment of a Commit #1 memory's
    reliability, from the evidence available when it was assessed.

    quality_score and confidence are both normalized to
    backend.llm.evaluation_scoring's own [MIN_SCORE, MAX_SCORE] -- the
    same 0.0-1.0 scale that module, backend.llm.context_retrieval, and
    Commit #3's relevance scorer already use, one score convention for the
    whole repository. The two are deliberately distinct: quality_score is
    what the evidence says about the memory (how favorable it is on
    balance), confidence is how much that evidence is worth trusting (how
    much of it there is, whether it agrees with itself, and how stale it
    might be) -- a memory backed by one lone success and a memory backed
    by ten consistent ones can share the same quality_score while having
    very different confidence.

    evidence_count is how many individual signals (the memory's own
    outcome, each feedback record, each consolidated source) fed the
    assessment. assessment_reason is a human-readable breakdown of what
    those signals were and how they combined -- assessment provenance,
    the same explainability convention Commit #3's ScoredMemory.reason
    already establishes. assessed_at is when this particular judgment was
    made; assess()ing the same memory_id again later, as more feedback
    accumulates or simply as it ages, can produce a different result --
    this is a snapshot, never a permanent verdict.
    """

    memory_id: str
    quality_score: float
    confidence: float
    evidence_count: int
    assessment_reason: str
    assessed_at: datetime
