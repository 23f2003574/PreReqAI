from datetime import datetime, timezone

from backend.agent_strategy_library import ACTIVE, LLMAgentStrategyService
from backend.agent_strategy_scoring import LLMAgentStrategyScorer

from .in_memory_store import InMemoryLLMAgentStrategyLifecycleStore
from .models import (
    DEPRECATED,
    MAX_DEPRECATED_SCORE,
    MIN_TRUSTED_CONFIDENCE,
    MIN_TRUSTED_SCORE,
    TRUSTED,
    LLMAgentStrategyLifecycleDecision,
)
from .store import LLMAgentStrategyLifecycleStore


class LLMAgentStrategyLifecycleEvaluator:
    """Judges a Commit #1 strategy's health from its accumulated Commit
    #3/#4 evidence, and records whether it should be treated as ACTIVE,
    TRUSTED, or DEPRECATED.

    Not a second lifecycle system: eligibility is entirely Commit #4's
    own LLMAgentStrategyScorer.score() -- score and confidence, which
    already fold in every recorded Commit #3 outcome, recency-weighting,
    evidence volume, and agreement between contradictory outcomes. This
    evaluator adds only a status decision on top of that judgment,
    recorded as an append-only LLMAgentStrategyLifecycleDecision history
    (the same shape backend.agent_memory_promotion's own promotion
    records already use for memories) rather than a field mutated on the
    strategy itself. A strategy with no decision on record at all is
    ACTIVE by convention -- Commit #1's own default/base status, reused
    as-is rather than a redundant "candidate" synonym.

    evaluate() never calls Commit #1's create()/update()/archive() or
    Commit #3's record(): the underlying LLMAgentStrategy (its
    strategy_data, source_memory_ids, and Commit #1's own ACTIVE/ARCHIVED
    status) and every outcome behind it are never mutated by a lifecycle
    decision -- this evaluator's ACTIVE/TRUSTED/DEPRECATED tier is
    layered entirely alongside Commit #1's own record, never inside it.

    Promotion (-> TRUSTED) and deprecation (-> DEPRECATED) share one
    symmetric evidence bar -- score and confidence each cleared in the
    matching direction -- reusing the exact MIN_TRUSTED_SCORE/
    MIN_TRUSTED_CONFIDENCE values backend.agent_memory_promotion already
    established for the analogous memory decision. Confidence is what
    actually enforces "require sufficient evidence": Commit #4's own
    confidence formula cannot clear 0.7 from a single outcome (evidence
    alone, at perfect agreement, needs at least two), so neither a single
    success nor a single failure can ever move a strategy off ACTIVE on
    its own -- "repeated failures" (or repeated successes) is what the
    confidence bar actually requires.

    DEPRECATED is sticky: once a strategy has been evaluated as
    DEPRECATED, evaluate() keeps recording DEPRECATED on every later call,
    whatever new evidence accumulates -- the same reasoning
    backend.agent_memory_promotion.LLMAgentMemoryPromoter already applies
    (deprecation is a deliberate decision; no automatic learning loop
    reverses it). ACTIVE and TRUSTED are not sticky in this way: a
    strategy can move between them freely as new evidence shifts its
    score/confidence, since neither represents an irreversible judgment.
    """

    def __init__(
        self,
        strategy_service: LLMAgentStrategyService,
        scorer: LLMAgentStrategyScorer,
        store: LLMAgentStrategyLifecycleStore = None,
    ):
        self._strategy_service = strategy_service
        self._scorer = scorer
        self.store = store if store is not None else InMemoryLLMAgentStrategyLifecycleStore()

    def evaluate(self, strategy_id: str, now: datetime = None) -> LLMAgentStrategyLifecycleDecision:
        """Judge strategy_id from its currently available evidence, and
        append the resulting decision.

        Raises:
            UnknownAgentStrategyError: If strategy_id was never created by
                Commit #1 (propagated, not wrapped)
        """
        self._strategy_service.get(strategy_id)
        now = now or datetime.now(timezone.utc)

        history = self.store.list_for_strategy(strategy_id)
        previous_status = history[-1].status if history else ACTIVE

        score = self._scorer.score(strategy_id, now=now)

        if previous_status == DEPRECATED:
            status = DEPRECATED
            reason = "strategy is deprecated; reversal is not automatic"
        elif score.score <= MAX_DEPRECATED_SCORE and score.confidence >= MIN_TRUSTED_CONFIDENCE:
            status = DEPRECATED
            reason = (
                f"score={score.score:.3f} <= {MAX_DEPRECATED_SCORE} and "
                f"confidence={score.confidence:.3f} >= {MIN_TRUSTED_CONFIDENCE} ({score.reason})"
            )
        elif score.score >= MIN_TRUSTED_SCORE and score.confidence >= MIN_TRUSTED_CONFIDENCE:
            status = TRUSTED
            reason = (
                f"score={score.score:.3f} >= {MIN_TRUSTED_SCORE} and "
                f"confidence={score.confidence:.3f} >= {MIN_TRUSTED_CONFIDENCE} ({score.reason})"
            )
        else:
            status = ACTIVE
            reason = (
                f"insufficient evidence for a trusted or deprecated verdict "
                f"(score={score.score:.3f}, confidence={score.confidence:.3f}); ({score.reason})"
            )

        decision = LLMAgentStrategyLifecycleDecision(
            strategy_id=strategy_id, previous_status=previous_status, status=status, reason=reason,
            score=score.score, confidence=score.confidence, evidence_count=score.evidence_count,
            succeeded_count=score.succeeded_count, failed_count=score.failed_count, decided_at=now,
        )
        return self.store.save(decision)

    def evaluate_many(self, strategy_ids: list, now: datetime = None) -> list:
        """evaluate() every strategy_id, all judged as of the same `now` --
        so a batch reflects one consistent point in time rather than
        drifting recency as the loop runs."""
        now = now or datetime.now(timezone.utc)
        return [self.evaluate(strategy_id, now=now) for strategy_id in strategy_ids]
