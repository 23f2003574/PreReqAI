from backend.agent_strategy_library import ARCHIVED, LLMAgentStrategyService
from backend.llm.context_retrieval import searchable_text, tokenize


def score_strategy(strategy, query: str) -> float:
    """Deterministic keyword-overlap relevance of one strategy to a query.

    Reuses backend.llm.context_retrieval's own tokenize()/searchable_text() --
    the exact case-insensitive token-overlap convention Commit #2 (of the
    memory series)'s score_memory() and backend.llm.context_retrieval's own
    score_context() already use -- rather than a second relevance system,
    and without touching either. name, description, and strategy_data are
    all searched, since (unlike LLMAgentMemory, which has only content) a
    strategy's own name and description are as much a part of what a
    caller is searching for as its structured strategy_data.
    """
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return 0.0
    haystack = (
        set(tokenize(searchable_text(strategy.name)))
        | set(tokenize(searchable_text(strategy.description)))
        | set(tokenize(searchable_text(strategy.strategy_data)))
    )
    matched = query_tokens & haystack
    return round(len(matched) / len(query_tokens), 6)


class LLMAgentStrategyRetriever:
    """Finds Commit #1 strategies relevant to a new agent task.

    Not a second retrieval framework: relevance ranking reuses
    backend.llm.context_retrieval's own tokenize()/searchable_text()
    (score_strategy(), above) -- the repository's one deterministic,
    embedding-free keyword-overlap scorer, the same primitive
    backend.agent_memory_retrieval's own score_memory() already reuses --
    and scope isolation, persistence, and status filtering are delegated
    entirely to Commit #1's own LLMAgentStrategyService.list(); this
    service holds no store of its own and never reads a strategy
    belonging to any scope other than the one retrieve() is called with.
    Read-only throughout: neither retrieve() nor rank() ever calls
    create()/update()/archive(), so looking up a strategy can never
    create, change, or retire one.

    Every result stays the exact LLMAgentStrategy Commit #1 stored --
    source_memory_ids (and every other field) passes through untouched,
    so a caller can always trace a retrieved strategy back to the
    memories that justified it via Commit #1's own provenance().
    """

    def __init__(self, strategy_service: LLMAgentStrategyService):
        self._strategy_service = strategy_service

    def rank(self, strategies: list, query: str) -> list:
        """strategies, best-first by relevance to query, ties broken deterministically.

        Ties (equal score, including two strategies that both score 0.0
        against an empty query) break by most-recently-created first, then
        by strategy_id -- the same deterministic convention
        backend.agent_memory_retrieval.LLMAgentMemoryRetriever.rank()
        already uses -- so repeated calls over the same input always
        return the same order.
        """
        if not isinstance(query, str):
            raise ValueError("query must be a string")

        scored = [(score_strategy(strategy, query), strategy) for strategy in strategies]
        scored.sort(key=lambda pair: (-pair[0], -pair[1].created_at.timestamp(), pair[1].strategy_id))
        return [strategy for _score, strategy in scored]

    def retrieve(self, scope_id: str, query: str, limit: int = None, status: str = None) -> list:
        """The strategies in scope_id relevant to query, best first.

        status, when omitted, retrieves every status Commit #1 knows
        about and then drops ARCHIVED ones -- archived strategies are
        excluded by default, never returned unless a caller explicitly
        asks for them. Passing status explicitly (e.g. ARCHIVED) hands
        that exact filter straight to Commit #1's own list(), so a caller
        who does want archived strategies (an audit trail, say) can still
        reach them.

        Raises:
            ValueError: If query is not a string, scope_id fails Commit
                #1's own validation, or limit is not a positive integer
                (all propagated from, or mirroring, Commit #1's own checks)
            InvalidStrategyStatusError: If status is given and is not one
                of Commit #1's own STATUSES (propagated from list())
        """
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0):
            raise ValueError("limit must be a positive integer")

        candidates = self._strategy_service.list(scope_id, status)
        if status is None:
            candidates = [strategy for strategy in candidates if strategy.status != ARCHIVED]

        ranked = self.rank(candidates, query)
        if limit is not None:
            ranked = ranked[:limit]
        return ranked
