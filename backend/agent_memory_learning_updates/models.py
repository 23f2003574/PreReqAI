from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class LLMAgentMemoryLearningMetadata:
    """The accumulated, evidence-backed learning tally for one Commit #1 memory.

    Nothing here is a fact about the memory's content -- it is bookkeeping
    about the evidence that has been applied to it: how many distinct
    pieces of evidence favored it (supporting_evidence_count) versus
    disfavored it (contradicting_evidence_count), and how many of those
    specifically came from a later reuse of the memory rather than its own
    origin (successful_use_count/failed_use_count -- both are always a
    subset of supporting/contradicting, never a separate tally that could
    disagree with them). Both sides are always reported, never netted
    against each other into one number: a memory with 3 supporting and 2
    contradicting pieces of evidence is not silently reported as "net +1."

    evidence_refs is every (source, identity) pair -- a Commit #8 signal's
    own evidence["source"] and its feedback_id/execution_id -- that has
    ever been counted into this tally, sorted for a stable, deterministic
    read. It is what makes this metadata traceable back to the concrete
    records it was built from, and what apply_signals() checks against to
    stay idempotent: a piece of evidence already in evidence_refs is never
    counted a second time, however many times it is reapplied.
    """

    memory_id: str
    supporting_evidence_count: int
    contradicting_evidence_count: int
    successful_use_count: int
    failed_use_count: int
    evidence_refs: tuple
    last_updated_at: Optional[datetime]


@dataclass(frozen=True)
class LLMAgentMemoryLearningUpdateResult:
    """What update_from_execution() found for one execution_id.

    memory_id and metadata are None whenever no memory can be resolved
    from execution_id alone -- there is no existing index from an
    execution_id back to whichever memory (if any) it produced or
    relates to, the same limitation Commit #8's own extract() documents.
    A caller who already knows the memory_id an execution relates to uses
    apply_signals() or update_from_memory() directly instead.
    """

    execution_id: str
    memory_id: Optional[str]
    signals: list
    metadata: Optional[LLMAgentMemoryLearningMetadata]
    updated_at: datetime
