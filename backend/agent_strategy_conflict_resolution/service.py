from backend.agent_strategy_library import ACTIVE
from backend.agent_strategy_lifecycle import DEPRECATED, TRUSTED, LLMAgentStrategyLifecycleStore

from .models import (
    EVIDENCE,
    TASK_CONSTRAINT,
    UNRESOLVED,
    LLMAgentStrategyConflict,
    LLMAgentStrategyConflictDecision,
    LLMAgentStrategyConflictResolution,
)

# Lower ranks are preferred, the same shape
# backend.agent_memory_application's own _STATUS_RANK already uses for
# TRUSTED/CANDIDATE/DEPRECATED -- reused here for Commit #9's own
# ACTIVE/TRUSTED/DEPRECATED tier rather than a second status-preference
# scheme.
_STATUS_RANK = {TRUSTED: 0, ACTIVE: 1, DEPRECATED: 2}


def _declared_conflict(strategy_a, strategy_b):
    """Whichever explicit, structural signal in strategy_data marks these
    two strategies incompatible, or None. Never inferred from natural-
    language similarity between description/strategy_data -- that would
    need an LLM call this module never makes; a conflict is only ever one
    a strategy's own author declared.
    """
    data_a = strategy_a.strategy_data if isinstance(strategy_a.strategy_data, dict) else {}
    data_b = strategy_b.strategy_data if isinstance(strategy_b.strategy_data, dict) else {}

    conflicts_with_a = set(data_a.get("conflicts_with") or [])
    conflicts_with_b = set(data_b.get("conflicts_with") or [])
    if strategy_b.strategy_id in conflicts_with_a or strategy_a.strategy_id in conflicts_with_b:
        return "strategy_data declares an explicit conflicts_with reference between these strategies"

    group_a = data_a.get("exclusive_group")
    group_b = data_b.get("exclusive_group")
    if group_a is not None and group_a == group_b:
        return f"both strategies share exclusive_group {group_a!r}"

    return None


class LLMAgentStrategyConflictResolver:
    """Detects and resolves incompatible Commit #5 strategy selections
    before they ever reach the real planner.

    Not a second planning system: detect_conflicts()/resolve_conflicts()
    never call backend.agent_task_planning.LLMAgentPlanningService, never
    produce a plan of their own, and never mutate a strategy, outcome, or
    lifecycle record -- this sits entirely between Commit #5's selection
    and Commit #6's application, filtering the list Commit #6 would
    otherwise apply unchanged. Compatibility is read directly from
    strategy_data (an explicit conflicts_with reference, or a shared
    exclusive_group) -- the same "only ever act on what was explicitly
    declared" discipline every other module here already keeps for
    anything that isn't a verified execution fact.

    Evidence-based resolution reuses two existing judgments as-is, never
    recomputing either: Commit #9's own lifecycle tier (read-only, via an
    optional LLMAgentStrategyLifecycleStore -- resolve_conflicts() never
    calls evaluate() itself, so resolving a conflict can never append a
    new lifecycle decision) ranked with the exact
    backend.agent_memory_application._STATUS_RANK shape, then Commit #5's
    own Commit #4 effectiveness score/confidence already carried on each
    LLMAgentStrategySelection. Explicit context requirements
    (required_strategy_ids) are checked first and always win over both,
    per Commit #10's own "explicit task requirements always win" rule.

    Every detected conflict produces exactly one
    LLMAgentStrategyConflictDecision, whatever the outcome -- a strategy
    is never dropped from `selected` without a decision explaining why,
    and a conflict that cannot be safely resolved (both sides explicitly
    required) is recorded as UNRESOLVED rather than guessed at. Given the
    same strategies and context, resolve_conflicts() always reaches the
    same decisions: ties that survive trust/status and effectiveness are
    broken by strategy_id, never left to iteration order or chance.
    """

    def __init__(self, lifecycle_store: LLMAgentStrategyLifecycleStore = None):
        self._lifecycle_store = lifecycle_store

    def _status_for(self, strategy) -> str:
        if self._lifecycle_store is None:
            return ACTIVE
        history = self._lifecycle_store.list_for_strategy(strategy.strategy_id)
        return history[-1].status if history else ACTIVE

    def detect_conflicts(self, strategies: list) -> list:
        """Every pairwise LLMAgentStrategyConflict among strategies --
        pure detection, no resolution. Order-independent: the same set of
        conflicting pairs is found regardless of the input list's order.

        Raises:
            ValueError: If strategies is not a list
        """
        if not isinstance(strategies, list):
            raise ValueError("strategies must be a list")

        conflicts = []
        for i in range(len(strategies)):
            for j in range(i + 1, len(strategies)):
                strategy_a = strategies[i].strategy
                strategy_b = strategies[j].strategy
                reason = _declared_conflict(strategy_a, strategy_b)
                if reason is not None:
                    pair = tuple(sorted((strategy_a.strategy_id, strategy_b.strategy_id)))
                    conflicts.append(LLMAgentStrategyConflict(strategy_ids=pair, reason=reason))
        return conflicts

    def _rank_by_evidence(self, selection_a, selection_b):
        """The stronger of two conflicting selections by trust/status
        then Commit #4 effectiveness, falling back to strategy_id when
        every other signal ties -- so this always returns a definite
        (winner, loser, reason), never an ambiguous result.
        """
        status_rank_a = _STATUS_RANK[self._status_for(selection_a.strategy)]
        status_rank_b = _STATUS_RANK[self._status_for(selection_b.strategy)]
        if status_rank_a != status_rank_b:
            winner, loser = (selection_a, selection_b) if status_rank_a < status_rank_b else (selection_b, selection_a)
            return winner, loser, "stronger trust/status tier"

        score_a, score_b = selection_a.effectiveness.score, selection_b.effectiveness.score
        if score_a != score_b:
            winner, loser = (selection_a, selection_b) if score_a > score_b else (selection_b, selection_a)
            return winner, loser, f"stronger effectiveness score ({max(score_a, score_b):.3f} vs {min(score_a, score_b):.3f})"

        confidence_a = selection_a.effectiveness.confidence
        confidence_b = selection_b.effectiveness.confidence
        if confidence_a != confidence_b:
            winner, loser = (
                (selection_a, selection_b) if confidence_a > confidence_b else (selection_b, selection_a)
            )
            return winner, loser, "more confident effectiveness evidence"

        winner, loser = sorted([selection_a, selection_b], key=lambda item: item.strategy.strategy_id)
        return winner, loser, "evidence-tied; resolved deterministically by strategy_id"

    def resolve_conflicts(self, strategies: list, context: dict = None) -> LLMAgentStrategyConflictResolution:
        """Filter strategies down to a conflict-free selection, recording
        every decision made along the way.

        context, when given, may carry "required_strategy_ids" -- an
        explicit task/project requirement that a strategy be kept.
        Per Commit #10's own rule, a required strategy always wins any
        conflict it is part of; if both sides of a conflict are required,
        neither can be safely dropped and the conflict is recorded
        UNRESOLVED, with both strategies kept in `selected`.

        Raises:
            ValueError: If strategies is not a list, or context is given
                and is not a dict
        """
        if not isinstance(strategies, list):
            raise ValueError("strategies must be a list")
        if context is not None and not isinstance(context, dict):
            raise ValueError("context must be a dict when given")
        required = set((context or {}).get("required_strategy_ids") or [])

        by_id = {selection.strategy.strategy_id: selection for selection in strategies}
        conflicts = self.detect_conflicts(strategies)

        decisions = []
        losers = set()

        for conflict in conflicts:
            id_a, id_b = conflict.strategy_ids
            a_required, b_required = id_a in required, id_b in required

            if a_required and b_required:
                decisions.append(
                    LLMAgentStrategyConflictDecision(
                        conflict=conflict, winner_strategy_id=None, loser_strategy_id=None,
                        resolution=UNRESOLVED,
                        reason=(
                            f"{id_a!r} and {id_b!r} are both explicitly required by context; "
                            f"this conflict cannot be safely auto-resolved"
                        ),
                    )
                )
                continue

            if a_required or b_required:
                winner_id, loser_id = (id_a, id_b) if a_required else (id_b, id_a)
                decisions.append(
                    LLMAgentStrategyConflictDecision(
                        conflict=conflict, winner_strategy_id=winner_id, loser_strategy_id=loser_id,
                        resolution=TASK_CONSTRAINT,
                        reason=f"{winner_id!r} is explicitly required by context; explicit task requirements always win",
                    )
                )
                losers.add(loser_id)
                continue

            winner, loser, reason = self._rank_by_evidence(by_id[id_a], by_id[id_b])
            decisions.append(
                LLMAgentStrategyConflictDecision(
                    conflict=conflict, winner_strategy_id=winner.strategy.strategy_id,
                    loser_strategy_id=loser.strategy.strategy_id, resolution=EVIDENCE, reason=reason,
                )
            )
            losers.add(loser.strategy.strategy_id)

        selected = [selection for selection in strategies if selection.strategy.strategy_id not in losers]
        return LLMAgentStrategyConflictResolution(selected=selected, conflicts=decisions)
