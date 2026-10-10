from datetime import datetime, timezone

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_memory_feedback import MAX_RATING, MIN_RATING, LLMAgentMemoryFeedbackService
from backend.llm.evaluation_scoring import MAX_SCORE, MIN_SCORE
from backend.llm.tool_execution import SUCCEEDED

from .models import LLMAgentMemoryQuality

# Weights sum to 1.0 when every evidence source is present, the same
# weighted-total convention Commit #3's relevance scorer already uses.
# When a source is absent (no feedback yet, never consolidated), the
# remaining weights are renormalized rather than treating the missing
# source as a neutral value -- a memory's score always reflects only the
# evidence that actually exists.
_OUTCOME_WEIGHT = 0.3
_FEEDBACK_WEIGHT = 0.5
_CONSOLIDATION_WEIGHT = 0.2

# How favorably each Commit #5 feedback_type reads on its own, on the same
# [MIN_SCORE, MAX_SCORE] scale as everything else here. "incorrect" and
# "failed" both read as 0.0 -- both say the memory should not be trusted
# as reusable knowledge, whatever nuance separates them.
_FEEDBACK_TYPE_SIGNAL = {
    "successful": MAX_SCORE,
    "useful": 0.75,
    "not_useful": 0.25,
    "incorrect": MIN_SCORE,
    "failed": MIN_SCORE,
}

# Staleness never drives confidence all the way to 0: a memory backed by
# strong, consistent, plentiful evidence is still worth something even if
# old, just less certain than the same evidence would be if fresh. Half
# of the (1.0 - floor) headroom is lost every _RECENCY_HALF_LIFE_DAYS.
_RECENCY_FLOOR = 0.5
_RECENCY_HALF_LIFE_DAYS = 60.0


def _feedback_value(feedback) -> float:
    """One feedback record's contribution, blending its categorical
    feedback_type with its optional numeric rating when both are given."""
    type_signal = _FEEDBACK_TYPE_SIGNAL[feedback.feedback_type]
    if feedback.rating is None:
        return type_signal
    normalized_rating = (feedback.rating - MIN_RATING) / (MAX_RATING - MIN_RATING)
    return (type_signal + normalized_rating) / 2


def _consolidation_sources(memory) -> list:
    """The Commit #4 "sources" a consolidated memory's content carries,
    or [] for an ordinary (never-consolidated) memory."""
    if isinstance(memory.content, dict) and memory.content.get("consolidated") is True:
        return memory.content.get("sources", [])
    return []


def _age_days(created_at: datetime, now: datetime) -> float:
    return max(0.0, (now - created_at).total_seconds() / 86400.0)


class LLMAgentMemoryQualityAssessor:
    """Judges whether a Commit #1 memory is reliable enough to influence a
    future execution, from the evidence already on record for it.

    Not a second evaluation subsystem: nothing here is stored, versioned,
    or re-derived by a new scoring pipeline -- assess() reads Commit #1's
    own LLMAgentMemoryService.get() for the memory's verified outcome,
    Commit #5's own LLMAgentMemoryFeedbackService.list_for_memory() for
    every piece of explicit feedback ever recorded against it, and (when
    the memory is itself Commit #4's output) its own content["sources"]
    for consolidation history -- three existing records, combined, never
    a fourth store of quality data. No LLM call is made or needed: every
    input is already a concrete record, and the combination is a fixed,
    documented formula.

    Kept deliberately apart from Commit #2/#3's retrieval path: assess()
    takes no query and never calls LLMAgentMemoryRetriever or
    LLMAgentMemoryRelevanceScorer -- quality is a property of the memory
    on its own evidence, not of how well it matches any particular
    request. Read-only throughout: assess() never writes to any store, so
    a memory's own record is never mutated because its quality changed --
    two calls to assess() for the same memory_id at the same `now`, with
    the same feedback on record, always return the identical result.

    quality_score never trusts one signal alone: a memory backed only by
    its own SUCCEEDED execution and nothing else scores a full 1.0
    quality_score (that single signal is all there is), but confidence
    stays modest (evidence_count == 1) until more evidence -- feedback or
    consolidated reuse -- accumulates. Negative or contradictory feedback
    both pull quality_score down (via _FEEDBACK_TYPE_SIGNAL) and pull
    confidence down further still, through an agreement penalty: feedback
    that is unanimous keeps full confidence, feedback split between
    favorable and unfavorable earns less, regardless of quality_score's
    own average.
    """

    def __init__(self, memory_service: LLMAgentMemoryService, feedback_service: LLMAgentMemoryFeedbackService):
        self._memory_service = memory_service
        self._feedback_service = feedback_service

    def assess(self, memory_id: str, now: datetime = None) -> LLMAgentMemoryQuality:
        """Assess one memory from its currently available evidence.

        Raises:
            UnknownAgentMemoryError: If memory_id was never recorded by
                Commit #1 (propagated, not wrapped)
        """
        memory = self._memory_service.get(memory_id)
        feedback_records = self._feedback_service.list_for_memory(memory_id)
        now = now or datetime.now(timezone.utc)

        components = []
        evidence_count = 1
        agreement_factor = 1.0

        own_outcome_value = MAX_SCORE if memory.outcome == SUCCEEDED else MIN_SCORE
        components.append((_OUTCOME_WEIGHT, own_outcome_value, f"own outcome={memory.outcome}"))

        if feedback_records:
            values = [_feedback_value(feedback) for feedback in feedback_records]
            feedback_component = sum(values) / len(values)
            components.append(
                (_FEEDBACK_WEIGHT, feedback_component, f"{len(values)} feedback record(s), avg={feedback_component:.3f}")
            )
            evidence_count += len(values)

            # Agreement: what share of feedback falls on the majority side
            # of "favorable" (>= the midpoint) versus "unfavorable" -- 1.0
            # when every record agrees, as low as 0.5 when evenly split.
            favorable = sum(1 for value in values if value >= (MIN_SCORE + MAX_SCORE) / 2)
            unfavorable = len(values) - favorable
            agreement_factor = max(favorable, unfavorable) / len(values)

        sources = _consolidation_sources(memory)
        if sources:
            succeeded = sum(1 for source in sources if source.get("outcome") == SUCCEEDED)
            consolidation_component = succeeded / len(sources)
            components.append(
                (_CONSOLIDATION_WEIGHT, consolidation_component,
                 f"{len(sources)} consolidated source(s), {succeeded} succeeded")
            )
            evidence_count += len(sources)

        total_weight = sum(weight for weight, _value, _label in components)
        quality_score = round(
            sum(weight * value for weight, value, _label in components) / total_weight, 6
        )

        evidence_confidence = 1.0 - 0.5 ** evidence_count
        recency_factor = _RECENCY_FLOOR + (1.0 - _RECENCY_FLOOR) * 0.5 ** (
            _age_days(memory.created_at, now) / _RECENCY_HALF_LIFE_DAYS
        )
        confidence = round(
            min(MAX_SCORE, max(MIN_SCORE, evidence_confidence * agreement_factor * recency_factor)), 6
        )

        reason = (
            "; ".join(label for _weight, _value, label in components)
            + f"; agreement={agreement_factor:.3f}; recency={recency_factor:.3f}"
        )

        return LLMAgentMemoryQuality(
            memory_id=memory_id,
            quality_score=quality_score,
            confidence=confidence,
            evidence_count=evidence_count,
            assessment_reason=reason,
            assessed_at=now,
        )

    def assess_batch(self, memory_ids: list, now: datetime = None) -> list:
        """assess() every memory_id, all judged as of the same `now` --
        so a batch reflects one consistent point in time rather than
        drifting recency as the loop runs."""
        now = now or datetime.now(timezone.utc)
        return [self.assess(memory_id, now=now) for memory_id in memory_ids]
