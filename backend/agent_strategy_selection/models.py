from dataclasses import dataclass

from backend.agent_strategy_library import LLMAgentStrategy
from backend.agent_strategy_scoring import LLMAgentStrategyScore


@dataclass(frozen=True)
class LLMAgentStrategySelection:
    """One Commit #1 strategy select() judged worth surfacing for a task,
    plus everything that judgment rests on.

    strategy is the exact, unmodified LLMAgentStrategy Commit #1 stored --
    nothing about it is copied or redacted, so source_memory_ids (and
    every other field) stays reachable exactly as Commit #1 recorded it.
    effectiveness is the exact Commit #4 LLMAgentStrategyScore this
    selection was judged against -- its own evidence_count/reason carry
    the "available evidence" half of why this strategy was (or, filtered
    out entirely, was not) selected. relevance_score is this task's own
    Commit #2 score_strategy() match. combined_score is the ranking value
    select() actually sorts by; reason is a human-readable breakdown of
    how relevance and effectiveness combined -- the same explainability
    convention Commit #3's ScoredMemory.reason and Commit #6's
    LLMAgentMemoryQuality.assessment_reason already establish.

    This is advisory data only: nothing here is a plan, and nothing about
    selecting a strategy ever calls the real planner or mutates it -- the
    planner remains entirely authoritative over what a task's plan
    actually is.
    """

    strategy: LLMAgentStrategy
    relevance_score: float
    effectiveness: LLMAgentStrategyScore
    combined_score: float
    reason: str
