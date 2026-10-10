from backend.agent_strategy_library import ARCHIVED
from backend.agent_strategy_selection import LLMAgentStrategySelection

# The key apply() adds to an existing planning context dict. Namespaced so
# this service only ever adds its own key -- every other key an existing
# context dict already carries (including anything drawn from
# backend.llm.project_context or Commit #10's own CONTEXT_KEY,
# "agent_memories") is passed through untouched. This is the exact same
# `context: dict` parameter backend.agent_task_planning.
# LLMAgentPlanningService.create() already accepts and folds straight
# into its own prompt payload (see that service's own _build_prompt()) --
# the existing context-injection point, reused as-is rather than a new one.
CONTEXT_KEY = "strategy_guidance"


class CrossScopeApplicationError(ValueError):
    """Raised when selected_strategies mixes strategies from more than one
    scope_id -- apply() refuses to merge cross-scope guidance into a
    single planning context, whatever a caller passed it."""


def _evidence_entry(selection: LLMAgentStrategySelection) -> dict:
    strategy = selection.strategy
    effectiveness = selection.effectiveness
    return {
        "strategy_id": strategy.strategy_id,
        "scope_id": strategy.scope_id,
        "name": strategy.name,
        "description": strategy.description,
        "strategy_data": strategy.strategy_data,
        "status": strategy.status,
        "relevance_score": selection.relevance_score,
        "combined_score": selection.combined_score,
        "effectiveness": {
            "score": effectiveness.score,
            "confidence": effectiveness.confidence,
            "evidence_count": effectiveness.evidence_count,
            "succeeded_count": effectiveness.succeeded_count,
            "failed_count": effectiveness.failed_count,
            "reason": effectiveness.reason,
        },
        "provenance": {"source_memory_ids": list(strategy.source_memory_ids)},
        "reason": selection.reason,
        "advisory": True,
    }


class LLMAgentStrategyApplicator:
    """Applies Commit #5's already-selected strategies to an existing
    agent planning context, as structured, advisory guidance.

    Not a second context or planning framework: apply() folds its result
    into whatever `context: dict` a caller is already assembling for
    backend.agent_task_planning.LLMAgentPlanningService.create() -- the
    real, unmodified planning entry point, and the exact point that
    service already treats as optional supporting information in its own
    prompt payload (create()'s own `context` parameter). Nothing here
    changes that service, its system prompt, or how it decides a plan;
    apply() only ever adds one namespaced key (CONTEXT_KEY) to a context
    dict, the same additive convention Commit #10's own
    backend.agent_memory_application.LLMAgentMemoryApplicator already
    established for memory.

    apply() takes selection, not scope_id/task: Commit #5's
    LLMAgentStrategySelector.select() has already done relevance ranking,
    effectiveness scoring, archived-exclusion, and confidence-gating by
    the time its result reaches here, so this service holds no store or
    scorer of its own and calls no other service -- it is a pure
    transformation of already-selected data into one structured guidance
    entry per strategy, plus one further, defensive check of its own:
    any ARCHIVED strategy still present in selected_strategies is
    excluded here too (defense in depth, never trusting a caller to have
    filtered it already), and strategies spanning more than one scope_id
    are refused outright rather than silently merged into one context.

    Every entry stays traceable back to Commit #1's own record --
    source_memory_ids (Commit #1's own provenance), the Commit #4
    effectiveness breakdown, and Commit #5's own relevance/combined
    scores and reason are all included verbatim, never summarized away.
    Every entry is also tagged advisory=True: nothing here is phrased as
    an instruction, and `task` itself (the actual task requirement) is
    never touched -- create()'s own prompt payload keeps task and context
    as separate fields, so existing task requirements are never
    superseded by strategy guidance.

    apply() only ever reads its arguments -- no strategy, outcome, or
    plan is created, changed, or removed by applying selected strategies
    to a context, and task_context itself is never mutated: a shallow
    copy is returned, with every existing key untouched and only
    CONTEXT_KEY added (or refreshed, if a caller passed one in already).
    """

    def apply(self, task_context: dict, selected_strategies: list) -> dict:
        """selected_strategies, structured as guidance and merged into
        task_context under CONTEXT_KEY -- ready to pass straight to
        LLMAgentPlanningService.create(task, enriched_context).

        Raises:
            ValueError: If task_context is given and is not a dict, or
                selected_strategies is not a list
            CrossScopeApplicationError: If selected_strategies contains
                strategies from more than one scope_id
        """
        if task_context is not None and not isinstance(task_context, dict):
            raise ValueError("task_context must be a dict when given")
        if not isinstance(selected_strategies, list):
            raise ValueError("selected_strategies must be a list")

        active = [
            selection for selection in selected_strategies
            if selection.strategy.status != ARCHIVED
        ]

        scope_ids = {selection.strategy.scope_id for selection in active}
        if len(scope_ids) > 1:
            raise CrossScopeApplicationError(
                f"selected_strategies span multiple scopes: {sorted(scope_ids)}"
            )

        enriched = dict(task_context) if task_context else {}
        enriched[CONTEXT_KEY] = [_evidence_entry(selection) for selection in active]
        return enriched
