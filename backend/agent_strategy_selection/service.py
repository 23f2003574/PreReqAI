from datetime import datetime, timezone

from backend.agent_strategy_retrieval import LLMAgentStrategyRetriever, score_strategy
from backend.agent_strategy_scoring import LLMAgentStrategyScorer

from .models import LLMAgentStrategySelection

# Weights sum to 1.0, so a strategy that is a perfect keyword match *and*
# has a perfect effectiveness record scores exactly 1.0 and nothing scores
# above it -- the same weighted-total convention
# backend.agent_memory_relevance_scoring's own relevance scorer already
# uses. Kept symmetric: task relevance and a proven track record are
# treated as equally important inputs to selection, neither one able to
# fully outweigh the other on its own.
_RELEVANCE_WEIGHT = 0.5
_EFFECTIVENESS_WEIGHT = 0.5

# The actual mechanism behind "do not select unsupported/low-confidence
# strategies merely because they are relevant": a strategy with less
# confidence than this is excluded from selection outright, however
# strong its keyword match, rather than merely down-ranked. A strategy
# with zero recorded Commit #3 outcomes scores exactly 0.0 confidence
# (Commit #4's own baseline) and is always excluded; one with even a
# single recorded outcome clears this bar (Commit #4's evidence-volume
# factor puts one outcome's confidence at 0.5) and is judged on its
# combined score like everything else.
MIN_SELECTION_CONFIDENCE = 0.3


class LLMAgentStrategySelector:
    """Selects the Commit #1 strategies worth surfacing for a new agent
    task, from task relevance and Commit #4 effectiveness combined.

    Not a second retrieval framework: candidate discovery, scope
    isolation, and archived-exclusion are entirely Commit #2's own
    LLMAgentStrategyRetriever.retrieve() (reused as-is, at no limit, so
    selection sees every eligible candidate before applying its own
    confidence gate and limit), and relevance is scored with Commit #2's
    own score_strategy() -- the identical keyword-overlap function
    retrieve()'s internal ranking already uses, so a strategy's
    relevance_score here always agrees with why retrieve() ordered it
    where it did. Effectiveness is entirely Commit #4's own
    LLMAgentStrategyScorer.score() -- nothing here re-derives outcome
    history a second way.

    select() only ever reads (LLMAgentStrategyRetriever.retrieve(),
    LLMAgentStrategyScorer.score()) -- no strategy, outcome, or plan is
    ever created, changed, or removed by selecting from it, and select()
    never calls the real backend.agent_task_planning.LLMAgentPlanningService
    itself. This is advisory input for whatever assembles a planning
    call, never a replacement for one: the planner remains entirely
    authoritative over the plan it actually produces.
    """

    def __init__(self, retriever: LLMAgentStrategyRetriever, scorer: LLMAgentStrategyScorer):
        self._retriever = retriever
        self._scorer = scorer

    def select(
        self, scope_id: str, task_context: str, limit: int = None, now: datetime = None
    ) -> list:
        """The strategies in scope_id worth surfacing for task_context, best first.

        Combines each candidate's task relevance (Commit #2's own
        score_strategy()) with its Commit #4 effectiveness score, weighted
        evenly. A candidate whose effectiveness confidence falls below
        MIN_SELECTION_CONFIDENCE is dropped entirely before ranking --
        relevance alone can never earn a strategy with no real evidence
        behind it a spot in the result. Archived strategies never reach
        this method at all: Commit #2's own retrieve() excludes them by
        default, and this method never overrides that.

        Ties (equal combined_score) break by most-recently-created
        strategy first, then by strategy_id -- the same deterministic
        convention every ranking method in this repository already uses --
        so repeated calls over the same evidence always return the same
        order.

        Raises:
            ValueError: If task_context is not a string, scope_id fails
                Commit #1's own validation, or limit is not a positive
                integer (propagated from, or mirroring, Commit #2's own
                checks)
        """
        if not isinstance(task_context, str):
            raise ValueError("task_context must be a string")
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0):
            raise ValueError("limit must be a positive integer")

        now = now or datetime.now(timezone.utc)

        # No limit here: selection applies its own confidence gate and
        # limit only after scoring every eligible candidate, so a
        # caller's `limit` always describes genuinely selected strategies,
        # never merely the top-N relevant ones before effectiveness is
        # weighed in.
        candidates = self._retriever.retrieve(scope_id, task_context)

        selections = []
        for strategy in candidates:
            effectiveness = self._scorer.score(strategy.strategy_id, now=now)
            if effectiveness.confidence < MIN_SELECTION_CONFIDENCE:
                continue

            relevance = score_strategy(strategy, task_context)
            combined = round(
                _RELEVANCE_WEIGHT * relevance + _EFFECTIVENESS_WEIGHT * effectiveness.score, 6
            )
            reason = (
                f"relevance={relevance:.3f}; effectiveness score={effectiveness.score:.3f} "
                f"confidence={effectiveness.confidence:.3f} ({effectiveness.reason}); "
                f"combined={combined:.3f}"
            )
            selections.append(
                LLMAgentStrategySelection(
                    strategy=strategy, relevance_score=relevance, effectiveness=effectiveness,
                    combined_score=combined, reason=reason,
                )
            )

        selections.sort(
            key=lambda item: (
                -item.combined_score,
                -item.strategy.created_at.timestamp(),
                item.strategy.strategy_id,
            )
        )

        if limit is not None:
            selections = selections[:limit]
        return selections
