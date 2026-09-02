from datetime import datetime, timezone

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_memory_promotion import CANDIDATE, DEPRECATED, TRUSTED, LLMAgentMemoryPromoter
from backend.agent_memory_relevance_scoring import LLMAgentMemoryRelevanceScorer
from backend.agent_memory_retrieval import LLMAgentMemoryQuery

# The number of applied memories, absent an explicit limit -- small enough
# that a planning prompt is never dominated by prior memory over the
# actual task, matching the "advisory, not an instruction" rule.
DEFAULT_LIMIT = 5

# The key apply() adds to an existing context dict. Namespaced so this
# service only ever adds its own key -- every other key an existing
# context dict already carries (including anything derived from Commit
# #1's own backend.llm.project_context) is passed through untouched.
CONTEXT_KEY = "agent_memories"

# Trusted memories are always preferred over candidates; deprecated ones
# are excluded well before this ever runs unless a caller explicitly asks
# otherwise, so DEPRECATED only appears here as a defensive fallback.
_STATUS_RANK = {TRUSTED: 0, CANDIDATE: 1, DEPRECATED: 2}


def _consolidated_source_ids(memories: list) -> set:
    """Every memory_id that some Commit #4 consolidated memory in
    `memories` already lists as one of its own sources -- the knowledge
    those originals carry is already represented by the consolidated
    summary, so including both would apply the same knowledge twice."""
    excluded = set()
    for memory in memories:
        if isinstance(memory.content, dict) and memory.content.get("consolidated") is True:
            for source in memory.content.get("sources", []):
                source_id = source.get("memory_id")
                if source_id:
                    excluded.add(source_id)
    return excluded


class LLMAgentMemoryApplicator:
    """Applies relevant, trusted Commit #1 memories to a new agent task as
    structured, advisory prior knowledge.

    Not a second agent-context pipeline: prepare() reads candidates
    through Commit #1's own LLMAgentMemoryService.list(scope_id) -- the
    same scope isolation every other memory operation already gets, so
    nothing outside scope_id can ever reach the result -- and ranks them
    with Commit #3's own LLMAgentMemoryRelevanceScorer.rank(), the
    repository's one relevance+outcome+recency scorer, rather than a new
    one. apply() feeds the result into
    backend.agent_task_planning.LLMAgentPlanningService.create()'s own
    existing `context: dict` parameter -- the actual point that service
    already assembles prior context from before asking the model for a
    plan -- under one namespaced key (CONTEXT_KEY), so every other key an
    existing context dict already carries (including anything drawn from
    backend.llm.project_context) stays exactly as the caller built it;
    that existing system remains authoritative for everything but this
    one key.

    Memory is advisory, never an instruction: every applied entry is
    tagged advisory=True, apply() never touches `task` itself, and
    LLMAgentPlanningService's own system prompt already treats `context`
    as optional supporting information -- nothing here changes that
    prompt or asks the planner to treat memory as binding.

    prepare()/apply() only ever read (list(), Commit #3's rank(),
    Commit #7's status_for()) -- no memory, feedback, or promotion record
    is created, changed, or removed by applying it, and no new storage of
    any kind is introduced here.
    """

    def __init__(
        self,
        memory_service: LLMAgentMemoryService,
        scorer: LLMAgentMemoryRelevanceScorer,
        promoter: LLMAgentMemoryPromoter,
    ):
        self._memory_service = memory_service
        self._scorer = scorer
        self._promoter = promoter

    def _status_rank(self, memory_id: str) -> int:
        return _STATUS_RANK[self._promoter.status_for(memory_id)]

    def _entry(self, scored) -> dict:
        memory = scored.memory
        return {
            "memory_id": memory.memory_id,
            "execution_id": memory.execution_id,
            "scope_id": memory.scope_id,
            "memory_type": memory.memory_type,
            "content": memory.content,
            "outcome": memory.outcome,
            "status": self._promoter.status_for(memory.memory_id),
            "relevance_score": scored.relevance_score,
            "reason": scored.reason,
            "advisory": True,
        }

    def prepare(
        self,
        scope_id: str,
        task: str,
        limit: int = DEFAULT_LIMIT,
        include_deprecated: bool = False,
        now: datetime = None,
    ) -> dict:
        """Retrieve, rank, and structure at most `limit` memories from
        scope_id relevant to `task`.

        1. Retrieve -- Commit #1's own list(scope_id); never anything
           outside scope_id.
        2. Prefer trusted -- Commit #7's status_for() reorders the
           (already relevance-ranked) candidates so every TRUSTED memory
           precedes every CANDIDATE one, preserving relevance order within
           each tier (a stable sort). DEPRECATED memories are dropped
           entirely unless include_deprecated=True is explicitly passed --
           existing policy (this default) excludes them, per the rule that
           deprecated memories are never injected unless explicitly
           permitted.
        3. Score -- Commit #3's own rank(): each entry keeps its
           relevance_score and reason, so provenance and ranking rationale
           both survive into the result.
        4. Deduplicate -- a memory listed as a Commit #4 consolidated
           record's own source is dropped when that consolidated record is
           also a candidate, so the same knowledge is never applied twice.
        5. Limit -- applied only after every filter above, so `limit`
           always describes genuinely distinct, policy-eligible memories.

        Raises:
            ValueError: If limit is not a positive integer
        """
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ValueError("limit must be a positive integer")

        candidates = self._memory_service.list(scope_id)

        if not include_deprecated:
            candidates = [
                memory for memory in candidates
                if self._promoter.status_for(memory.memory_id) != DEPRECATED
            ]

        candidates = [
            memory for memory in candidates
            if memory.memory_id not in _consolidated_source_ids(candidates)
        ]

        query = LLMAgentMemoryQuery(scope_id=scope_id, query=task)
        scored = self._scorer.rank(candidates, query, now=now)

        # Stable sort: preserves Commit #3's own relevance order within
        # each status tier, only reordering across tiers.
        preferred = sorted(scored, key=lambda item: self._status_rank(item.memory.memory_id))

        applied = preferred[:limit]
        return {
            "scope_id": scope_id,
            "task": task,
            "memories": [self._entry(item) for item in applied],
        }

    def apply(
        self,
        scope_id: str,
        task: str,
        context: dict = None,
        limit: int = DEFAULT_LIMIT,
        include_deprecated: bool = False,
        now: datetime = None,
    ) -> dict:
        """prepare()'s memory_context, merged into `context` under
        CONTEXT_KEY -- ready to pass straight to
        LLMAgentPlanningService.create(task, enriched_context).

        `context` itself is never mutated: a shallow copy is returned,
        with every existing key untouched and only CONTEXT_KEY added (or
        refreshed, if a caller passed one in already). Passing context=None
        (the common case: nothing else has been assembled yet) is
        equivalent to an empty dict.
        """
        memory_context = self.prepare(
            scope_id, task, limit=limit, include_deprecated=include_deprecated, now=now
        )
        enriched = dict(context) if context else {}
        enriched[CONTEXT_KEY] = memory_context
        return enriched
