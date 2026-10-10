from dataclasses import dataclass


@dataclass(frozen=True)
class LLMAgentMemoryConsolidationResult:
    """The outcome of consolidating one scope's worth of Commit #1 memories.

    groups holds the memory_ids consolidate_scope() found duplicated or
    related, one inner list per group, in the same order as consolidated
    (consolidated[i] is the new record produced from groups[i]).
    singleton_count is how many of the scope's non-consolidated memories
    had no duplicate/related match and were left exactly as they were --
    consolidate_scope() never touches them.
    """

    scope_id: str
    groups: list
    consolidated: list
    singleton_count: int
