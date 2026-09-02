from backend.agent_execution_memory import LLMAgentMemoryService
from backend.llm.context_retrieval import searchable_text, tokenize
from backend.llm.tool_execution import SUCCEEDED

from .models import LLMAgentMemoryConsolidationResult

# Jaccard overlap of the two memories' tokenized content, the same
# tokenize()/searchable_text() Commit #2/#3 already score relevance with.
# 0.5 means "at least as many shared distinct terms as differing ones" --
# high enough that two memories about genuinely different topics rarely
# cross it, low enough to still catch paraphrased repeats of the same
# execution knowledge (not just verbatim duplicates).
_DUPLICATE_SIMILARITY_THRESHOLD = 0.5


class EmptyConsolidationGroupError(ValueError):
    """Raised when consolidate() is given an empty group."""


class MixedScopeConsolidationError(ValueError):
    """Raised when consolidate() is given memories from more than one scope_id.

    Mirrors backend.llm.context_selection.MixedScopeError's own reasoning,
    applied here to memory instead of context: consolidation never
    silently merges knowledge across scopes.
    """


class MixedMemoryTypeConsolidationError(ValueError):
    """Raised when consolidate() is given memories of more than one memory_type.

    A single consolidated record can carry only one memory_type (Commit #1's
    own closed field), so a group spanning more than one is refused rather
    than guessing which type the result should claim.
    """


def _is_consolidated(memory) -> bool:
    """True for a memory find_duplicates()/consolidate() itself produced.

    Consolidated output is terminal: it is never treated as a candidate
    for further consolidation, so repeated runs never nest a consolidated
    summary inside another one.
    """
    return isinstance(memory.content, dict) and memory.content.get("consolidated") is True


def _similarity(a, b) -> float:
    """Deterministic Jaccard overlap between two memories' content tokens.

    Reuses backend.llm.context_retrieval's own tokenize()/searchable_text()
    -- the same primitives Commit #2's score_memory() and Commit #3's
    scorer already build on -- rather than a second text-comparison
    utility. Unlike score_memory() (query relevance, denominated by the
    query's own token count), this is symmetric: order never matters for
    "are these two memories duplicates of each other."
    """
    tokens_a = set(tokenize(searchable_text(a.content)))
    tokens_b = set(tokenize(searchable_text(b.content)))
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _rank_group(group: list) -> list:
    """group, strongest-first: a SUCCEEDED (proven) outcome before FAILED,
    then most recently created, then memory_id -- deterministic and
    reused as the same ordering for both "which content represents the
    group" and "which execution_id the consolidated record is linked to."
    """
    return sorted(
        group,
        key=lambda memory: (
            0 if memory.outcome == SUCCEEDED else 1,
            -memory.created_at.timestamp(),
            memory.memory_id,
        ),
    )


def _build_content(group: list, primary) -> dict:
    """The consolidated record's content: primary's own content as the
    summary, plus every group member's provenance and outcome -- so
    consolidation never discards a source's link back to its execution,
    and never collapses genuinely contradictory outcomes into one.
    """
    sources = [
        {
            "memory_id": memory.memory_id,
            "execution_id": memory.execution_id,
            "outcome": memory.outcome,
            "created_at": memory.created_at.isoformat(),
        }
        for memory in sorted(group, key=lambda memory: memory.memory_id)
    ]
    return {
        "consolidated": True,
        "summary": primary.content,
        "outcomes": sorted({memory.outcome for memory in group}),
        "sources": sources,
    }


class LLMAgentMemoryConsolidator:
    """Groups and merges Commit #1 memories so overlapping execution
    knowledge does not accumulate as noisy duplicates.

    Not a second context-management subsystem: duplicate detection reuses
    Commit #2/#3's own tokenize()/searchable_text() primitives (via
    _similarity(), above -- their symmetric counterpart to score_memory()),
    and every consolidated record is written through Commit #1's own
    LLMAgentMemoryService.record() -- the same execution-verification,
    content validation, and secret screening every other memory already
    goes through, rather than a second write path straight to the store.

    consolidate() reuses the strongest (SUCCEEDED-preferred, most recent)
    group member's own execution_id as the consolidated record's
    provenance link, exactly as record() already requires; nothing here
    is written for an execution that was never actually completed. Every
    other member's memory_id, execution_id, and outcome is preserved
    verbatim in the consolidated content's "sources"/"outcomes" -- a
    contradictory outcome (some SUCCEEDED, some FAILED, about the same
    knowledge) is recorded, never silently dropped or overwritten by the
    winning outcome.

    Kept deliberately separate from Commit #2/#3's retrieval path: this
    class never ranks or filters for a query, and neither
    LLMAgentMemoryRetriever nor LLMAgentMemoryRelevanceScorer is touched
    or called from here. A consolidated record is just another
    LLMAgentMemory once written, retrievable the same way as any other.

    Nothing here ever calls remove(): consolidation only ever adds a new,
    derived record. Every memory it consolidated stays exactly where
    Commit #1 stored it, reachable through get()/list() precisely as
    before.
    """

    def __init__(self, memory_service: LLMAgentMemoryService):
        self._memory_service = memory_service

    def find_duplicates(self, memories: list) -> list:
        """Cluster memories into duplicate/related groups, deterministically.

        Two memories are ever grouped only if they share both scope_id
        and memory_type (never across either -- the same "never silently
        merge across scopes" rule consolidate() itself enforces) and their
        content's Jaccard token overlap reaches
        _DUPLICATE_SIMILARITY_THRESHOLD. Grouping is transitive (if A~B
        and B~C, all three end up in one group even if A and C alone fall
        short of the threshold) via union-find, with union-by-smaller-id
        so the result never depends on input order.

        Only groups of two or more are returned -- a memory with no
        duplicate is not "a group of one" for this method; consolidate()
        still accepts a size-1 group and returns it unchanged, so a
        caller unioning find_duplicates()'s output with untouched
        singletons never needs a second code path.

        A memory this consolidator itself produced (its own "consolidated"
        content marker) is never treated as a candidate, so repeated
        consolidation never nests a summary inside another one.
        """
        candidates = sorted((m for m in memories if not _is_consolidated(m)), key=lambda m: m.memory_id)

        parent = {memory.memory_id: memory.memory_id for memory in candidates}

        def find(memory_id):
            while parent[memory_id] != memory_id:
                parent[memory_id] = parent[parent[memory_id]]
                memory_id = parent[memory_id]
            return memory_id

        def union(id_a, id_b):
            root_a, root_b = find(id_a), find(id_b)
            if root_a == root_b:
                return
            if root_a < root_b:
                parent[root_b] = root_a
            else:
                parent[root_a] = root_b

        for index, memory_a in enumerate(candidates):
            for memory_b in candidates[index + 1:]:
                if memory_a.scope_id != memory_b.scope_id or memory_a.memory_type != memory_b.memory_type:
                    continue
                if _similarity(memory_a, memory_b) >= _DUPLICATE_SIMILARITY_THRESHOLD:
                    union(memory_a.memory_id, memory_b.memory_id)

        groups_by_root = {}
        for memory in candidates:
            groups_by_root.setdefault(find(memory.memory_id), []).append(memory)

        groups = [
            sorted(group, key=lambda memory: memory.memory_id)
            for group in groups_by_root.values()
            if len(group) >= 2
        ]
        groups.sort(key=lambda group: group[0].memory_id)
        return groups

    def consolidate(self, group: list):
        """Merge one duplicate/related group into a single memory.

        A size-1 group is returned exactly as given -- there is nothing to
        merge, and this is never itself written as a new record.

        For a genuine group, the strongest member (see _rank_group())
        supplies the consolidated record's execution_id, scope_id,
        memory_type, and outcome; every member's own provenance and
        outcome is preserved in its content. Written through Commit #1's
        LLMAgentMemoryService.record(), so it passes the exact same
        execution-verification, JSON/secret validation every other memory
        does.

        Raises:
            EmptyConsolidationGroupError: If group is empty
            MixedScopeConsolidationError: If group spans more than one scope_id
            MixedMemoryTypeConsolidationError: If group spans more than one memory_type
        """
        if not group:
            raise EmptyConsolidationGroupError("cannot consolidate an empty group")

        scope_ids = {memory.scope_id for memory in group}
        if len(scope_ids) > 1:
            raise MixedScopeConsolidationError(f"group spans more than one scope: {sorted(scope_ids)}")

        memory_types = {memory.memory_type for memory in group}
        if len(memory_types) > 1:
            raise MixedMemoryTypeConsolidationError(
                f"group spans more than one memory_type: {sorted(memory_types)}"
            )

        if len(group) == 1:
            return group[0]

        primary = _rank_group(group)[0]
        content = _build_content(group, primary)

        return self._memory_service.record(
            primary.execution_id,
            {"scope_id": primary.scope_id, "memory_type": primary.memory_type, "content": content},
        )

    def consolidate_scope(self, scope_id: str) -> LLMAgentMemoryConsolidationResult:
        """Find and consolidate every duplicate/related group in scope_id.

        Delegates listing entirely to Commit #1's own
        LLMAgentMemoryService.list(scope_id) -- the same scope isolation
        every other memory operation already gets -- so this never reads,
        groups, or consolidates memory belonging to any other scope.
        """
        memories = self._memory_service.list(scope_id)
        groups = self.find_duplicates(memories)
        consolidated = [self.consolidate(group) for group in groups]

        grouped_ids = {memory.memory_id for group in groups for memory in group}
        singleton_count = sum(
            1
            for memory in memories
            if not _is_consolidated(memory) and memory.memory_id not in grouped_ids
        )

        return LLMAgentMemoryConsolidationResult(
            scope_id=scope_id,
            groups=[[memory.memory_id for memory in group] for group in groups],
            consolidated=consolidated,
            singleton_count=singleton_count,
        )
