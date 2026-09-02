from dataclasses import dataclass

from backend.agent_execution_memory import LLMAgentMemory


@dataclass(frozen=True)
class ScoredMemory:
    """One Commit #1 memory plus how the Commit #3 scorer rated it, and why.

    Mirrors backend.llm.context_retrieval.LLMContextMatch's own shape --
    subject, score, reason -- the repository's existing scored-result
    convention, applied here to LLMAgentMemory instead of
    LLMProjectContext. memory is the exact, unmodified record score()/
    rank() were given: nothing about it is copied, redacted, or changed,
    so relevance_score/reason are purely additive metadata layered
    alongside it, and memory.execution_id (Commit #1's own provenance
    link back to the originating execution) is always reachable straight
    off memory, unchanged by scoring.
    """

    memory: LLMAgentMemory
    relevance_score: float
    reason: str
