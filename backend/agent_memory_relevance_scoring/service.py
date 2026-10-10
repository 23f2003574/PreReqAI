from datetime import datetime, timezone

from backend.agent_memory_retrieval import LLMAgentMemoryQuery, score_memory
from backend.llm.tool_execution import SUCCEEDED

from .models import ScoredMemory

# Weights sum to 1.0, so a memory that matches on every signal scores
# exactly 1.0 and nothing scores above it. Relevance keeps the majority
# share deliberately: recency's own 0.15 ceiling can nudge two similarly
# relevant memories apart, but can never outweigh a strongly relevant
# match against a barely-relevant one (worst case, a same-day memory
# beats a year-old one by 0.15 -- less than a single 0.15-weighted point,
# and far less than the 0.55 relevance carries on its own).
_RELEVANCE_WEIGHT = 0.55
_TYPE_WEIGHT = 0.15
_OUTCOME_WEIGHT = 0.15
_RECENCY_WEIGHT = 0.15

# Recency half-life, in days: a memory created this long ago keeps half
# its recency credit. The decay is smooth and asymptotic to 0, never
# reaching it, so an old-but-relevant memory is never fully zeroed out by
# age alone -- it only ever loses its (bounded) 0.15 share of the total.
_RECENCY_HALF_LIFE_DAYS = 30.0

# A memory whose outcome was never explicitly asked for still leans
# toward a proven SUCCEEDED result over a FAILED one -- a documented,
# bounded bias, not a hard filter (Commit #2's own outcome_filter is
# still the only hard filter). A FAILED memory keeps most of its outcome
# credit: a captured failure pattern is still worth surfacing, just
# slightly behind a same-quality success by default.
_UNPREFERRED_OUTCOME_CREDIT = 0.6


def _recency_score(memory, now: datetime) -> float:
    age_seconds = max(0.0, (now - memory.created_at).total_seconds())
    age_days = age_seconds / 86400.0
    return 0.5 ** (age_days / _RECENCY_HALF_LIFE_DAYS)


def _type_score(memory, query: LLMAgentMemoryQuery) -> float:
    if not query.memory_types:
        return 1.0
    return 1.0 if memory.memory_type in query.memory_types else 0.0


def _outcome_score(memory, query: LLMAgentMemoryQuery) -> float:
    if query.outcome_filter is not None:
        return 1.0 if memory.outcome == query.outcome_filter else 0.0
    return 1.0 if memory.outcome == SUCCEEDED else _UNPREFERRED_OUTCOME_CREDIT


class LLMAgentMemoryRelevanceScorer:
    """Rates each Commit #1 memory against a Commit #2 query with one
    explicit, bounded, and explainable score.

    Not a second relevance system: query/content relevance is entirely
    Commit #2's own score_memory() (itself backend.llm.context_retrieval's
    deterministic keyword-overlap scorer, reused as-is). This adds only
    what Commit #2's plain text-overlap ranking has no notion of --
    combining that relevance with memory_type match, outcome, a bounded
    recency signal, and scope agreement into one weighted, documented
    total in [0.0, 1.0], so a caller sees a single number instead of
    juggling several.

    score()/rank() are pure functions of (memory, query, now): neither
    reads or writes any store, and neither touches `memory` itself --
    ScoredMemory only ever wraps the exact LLMAgentMemory object it was
    given, so the original record is always returned unchanged. Called
    twice with the same three inputs, both always return the same
    result -- `now` is a parameter precisely so a caller (or a test) can
    hold "the current time" fixed and get a reproducible score, rather
    than depending on the wall clock read from inside the method.
    """

    def score(self, memory, query: LLMAgentMemoryQuery, now: datetime = None) -> float:
        total, _reason = self._evaluate(memory, query, now or datetime.now(timezone.utc))
        return total

    def rank(self, memories: list, query: LLMAgentMemoryQuery, now: datetime = None) -> list:
        """memories, wrapped as ScoredMemory and sorted best-first.

        Ties (equal total score) break by most-recently-created first,
        then by memory_id -- the same deterministic convention Commit #2's
        LLMAgentMemoryRetriever.rank() already uses -- so repeated calls
        over the same input always return the same order.
        """
        now = now or datetime.now(timezone.utc)
        scored = [
            ScoredMemory(memory=memory, relevance_score=total, reason=reason)
            for memory, (total, reason) in (
                (memory, self._evaluate(memory, query, now)) for memory in memories
            )
        ]
        scored.sort(
            key=lambda item: (
                -item.relevance_score,
                -item.memory.created_at.timestamp(),
                item.memory.memory_id,
            )
        )
        return scored

    @staticmethod
    def _evaluate(memory, query: LLMAgentMemoryQuery, now: datetime):
        if memory.scope_id != query.scope_id:
            # Commit #2's own list(scope_id) already guarantees this never
            # happens for candidates it produced; scored at a hard 0.0
            # here too so a caller who scores memories from elsewhere
            # directly can never see an out-of-scope memory rank above an
            # in-scope one.
            return 0.0, f"scope mismatch: memory is in {memory.scope_id!r}, query is for {query.scope_id!r}"

        relevance = score_memory(memory, query.query)
        type_component = _type_score(memory, query)
        outcome_component = _outcome_score(memory, query)
        recency = _recency_score(memory, now)

        total = round(
            _RELEVANCE_WEIGHT * relevance
            + _TYPE_WEIGHT * type_component
            + _OUTCOME_WEIGHT * outcome_component
            + _RECENCY_WEIGHT * recency,
            6,
        )
        reason = (
            f"relevance={relevance:.3f} type={type_component:.3f} "
            f"outcome={outcome_component:.3f} recency={recency:.3f}"
        )
        return total, reason
