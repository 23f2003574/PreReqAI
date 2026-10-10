from backend.agent_execution_memory import VALID_MEMORY_TYPES, VALID_OUTCOMES, LLMAgentMemoryService
from backend.llm.context_retrieval import searchable_text, tokenize

from .models import LLMAgentMemoryQuery


class InvalidMemoryQueryError(ValueError):
    """Raised when a LLMAgentMemoryQuery names an unknown memory_type or
    outcome_filter, or a non-positive limit."""


def score_memory(memory, query: str) -> float:
    """Deterministic keyword-overlap relevance of one memory to a query.

    Reuses backend.llm.context_retrieval's own tokenize()/searchable_text()
    -- the exact case-insensitive token-overlap convention Commit #3's
    LLMContextRetrievalService already scores backend.llm.project_context
    with -- rather than a second relevance system, and without touching
    that module. An LLMProjectContext also folds its metadata into the
    haystack; LLMAgentMemory has no equivalent field, so only
    memory.content is searched.
    """
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return 0.0
    haystack = set(tokenize(searchable_text(memory.content)))
    matched = query_tokens & haystack
    return round(len(matched) / len(query_tokens), 6)


class LLMAgentMemoryRetriever:
    """Finds Commit #1 memories relevant to a new agent task.

    Not a second retrieval framework: relevance ranking reuses
    backend.llm.context_retrieval's own tokenize()/searchable_text()
    (score_memory(), above) -- the repository's one deterministic,
    embedding-free keyword-overlap scorer -- and scope isolation,
    persistence, and type filtering are delegated entirely to Commit #1's
    own LLMAgentMemoryService.list(); this service holds no store of its
    own and never reads memory belonging to any scope other than the one
    a query names. Read-only throughout: neither retrieve() nor rank()
    ever calls record()/remove(), so looking up memory can never create,
    change, or delete any.

    Every result stays the exact LLMAgentMemory Commit #1 stored --
    execution_id (and every other field) passes through untouched, so a
    caller can always trace a retrieved memory back to the execution it
    came from.

    An optional Commit #3 `scorer` (any object exposing
    `rank(memories, query, now=None) -> list[ScoredMemory-like]`, i.e.
    backend.agent_memory_relevance_scoring.LLMAgentMemoryRelevanceScorer)
    can be supplied to rank retrieve()'s already-filtered candidates by
    its richer, multi-signal score instead of this module's own plain
    text-overlap rank(). This is additive: omitting `scorer` reproduces
    this class's original behaviour exactly, and self.rank() itself is
    untouched either way -- retrieve() is the only method that ever
    consults `scorer`, kept as a duck-typed collaborator so this module
    never has to import Commit #3's package (which itself depends on this
    one).
    """

    def __init__(self, memory_service: LLMAgentMemoryService, scorer=None):
        self._memory_service = memory_service
        self._scorer = scorer

    def rank(self, memories: list, query: str) -> list:
        """memories, best-first by relevance to query, ties broken deterministically.

        Ties (equal score, including two memories that both score 0.0
        against an empty query) break by most-recently-created first, then
        by memory_id -- so repeated calls over the same input always
        return the same order.
        """
        if not isinstance(query, str):
            raise ValueError("query must be a string")

        scored = [(score_memory(memory, query), memory) for memory in memories]
        scored.sort(key=lambda pair: (-pair[0], -pair[1].created_at.timestamp(), pair[1].memory_id))
        return [memory for _score, memory in scored]

    def retrieve(self, query: LLMAgentMemoryQuery, now=None) -> list:
        """The memories in query.scope_id relevant to query, best first.

        `now` is passed through to a Commit #3 `scorer`, if one was
        supplied at construction; it is ignored otherwise (this module's
        own rank() has no recency signal to fix a clock for).

        Raises:
            InvalidMemoryQueryError: If memory_types/outcome_filter names
                something outside Commit #1's own closed vocabularies, or
                limit is not a positive integer
            ValueError: If query.query is not a string, or scope_id fails
                Commit #1's own validation (propagated from list())
        """
        self._validate(query)

        # Scope isolation is entirely Commit #1's own: list(scope_id) never
        # returns a memory recorded under a different scope_id, so this
        # service adds no isolation logic of its own to (or around) it.
        candidates = self._memory_service.list(query.scope_id)

        if query.memory_types:
            allowed_types = set(query.memory_types)
            candidates = [memory for memory in candidates if memory.memory_type in allowed_types]

        if query.outcome_filter is not None:
            candidates = [memory for memory in candidates if memory.outcome == query.outcome_filter]

        if self._scorer is not None:
            ranked = [scored.memory for scored in self._scorer.rank(candidates, query, now=now)]
        else:
            ranked = self.rank(candidates, query.query)

        if query.limit is not None:
            ranked = ranked[: query.limit]
        return ranked

    @staticmethod
    def _validate(query: LLMAgentMemoryQuery):
        if not isinstance(query, LLMAgentMemoryQuery):
            raise ValueError("query must be an LLMAgentMemoryQuery")

        if query.memory_types is not None:
            unknown = set(query.memory_types) - VALID_MEMORY_TYPES
            if unknown:
                raise InvalidMemoryQueryError(f"unknown memory_type(s): {sorted(unknown)}")

        if query.outcome_filter is not None and query.outcome_filter not in VALID_OUTCOMES:
            raise InvalidMemoryQueryError(
                f"outcome_filter {query.outcome_filter!r} is not one of {sorted(VALID_OUTCOMES)}"
            )

        if query.limit is not None:
            if not isinstance(query.limit, int) or isinstance(query.limit, bool) or query.limit <= 0:
                raise ValueError("limit must be a positive integer")
