from dataclasses import dataclass
from typing import Optional

# The kinds of judgment resolve_conflicts() can reach for one detected
# conflict. Deliberately small and closed, the same reasoning every other
# module's own status/category vocabulary here already documents.
TASK_CONSTRAINT = "task_constraint"
EVIDENCE = "evidence"
UNRESOLVED = "unresolved"
RESOLUTIONS = frozenset({TASK_CONSTRAINT, EVIDENCE, UNRESOLVED})


@dataclass(frozen=True)
class LLMAgentStrategyConflict:
    """One detected incompatibility between exactly two Commit #5-selected
    strategies -- pure detection, no judgment about which one should win.

    strategy_ids is always a 2-tuple, sorted so the same pair always
    produces the same LLMAgentStrategyConflict regardless of which order
    the two strategies appeared in the input list. reason explains what
    was found (a declared conflicts_with reference, or a shared
    exclusive_group) -- conflicts are only ever detected from strategy_data
    a strategy's own author declared, never inferred from natural-language
    similarity (which would need an LLM call this module never makes).
    """

    strategy_ids: tuple
    reason: str


@dataclass(frozen=True)
class LLMAgentStrategyConflictDecision:
    """What resolve_conflicts() decided for one LLMAgentStrategyConflict,
    and why -- always recorded, even when nothing was actually resolved.

    winner_strategy_id/loser_strategy_id are both None only when resolution
    is UNRESOLVED (both sides of the conflict were explicitly required by
    context, so neither can be safely dropped); otherwise winner is kept
    and loser is the one this decision drops from the final selection.
    resolution is one of RESOLUTIONS: TASK_CONSTRAINT when an explicit
    context requirement decided it (Commit #10's own "explicit task
    requirements always win" rule), EVIDENCE when trust/status and/or
    Commit #4 effectiveness decided it, UNRESOLVED when neither side could
    be safely dropped. This decision is never silently implied by a
    strategy's mere absence from `selected` -- every detected conflict
    produces exactly one of these, kept alongside the result.
    """

    conflict: LLMAgentStrategyConflict
    winner_strategy_id: Optional[str]
    loser_strategy_id: Optional[str]
    resolution: str
    reason: str


@dataclass(frozen=True)
class LLMAgentStrategyConflictResolution:
    """resolve_conflicts()'s complete result: the strategies that survive
    conflict resolution, and every decision made to get there.

    selected is the exact LLMAgentStrategySelection objects Commit #5
    already produced -- untouched, in their original relative order, so
    scores and provenance (source_memory_ids, effectiveness, reason) stay
    reachable exactly as Commit #5 computed them. conflicts is every
    LLMAgentStrategyConflictDecision reached, including UNRESOLVED ones --
    a strategy dropped from `selected` is always explainable by finding
    its strategy_id as a loser_strategy_id here, never merely inferred
    from its absence.
    """

    selected: list
    conflicts: list
