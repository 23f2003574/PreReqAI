from datetime import datetime, timezone

from backend.agent_strategy_effectiveness import LLMAgentStrategyOutcomeService
from backend.agent_strategy_library import LLMAgentStrategyService
from backend.llm.tool_execution import SUCCEEDED

from .models import LLMAgentStrategyScore

# No evidence at all is neither proof of success nor of failure -- score()
# reports this exact midpoint, at zero confidence, rather than guessing
# either extreme. The same "unproven, not yet judged" prior an empty
# LLMAgentMemoryQuality would want, kept local here since Commit #6 never
# needed one (a memory always has at least its own originating outcome).
_BASELINE_SCORE = 0.5

# Recency half-life, in days: an outcome this long ago keeps half its
# weight in the score -- the same decay shape
# backend.agent_memory_relevance_scoring's own recency signal already
# uses (same half-life value, kept as a local constant per this
# repository's convention of not sharing such constants across modules).
# Smooth and asymptotic to 0, so an old outcome is never fully zeroed out
# by age alone -- it only ever loses influence relative to newer evidence.
_RECENCY_HALF_LIFE_DAYS = 30.0


def _age_days(created_at: datetime, now: datetime) -> float:
    return max(0.0, (now - created_at).total_seconds() / 86400.0)


def _recency_weight(outcome, now: datetime) -> float:
    return 0.5 ** (_age_days(outcome.created_at, now) / _RECENCY_HALF_LIFE_DAYS)


class LLMAgentStrategyScorer:
    """Turns a Commit #1 strategy's Commit #3 outcome history into one
    deterministic, bounded effectiveness score retrieval can use.

    Not a second quality-assessment system: this deliberately mirrors
    backend.agent_memory_quality_assessment.LLMAgentMemoryQualityAssessor's
    own score/confidence split and its evidence-volume and agreement
    formulas, applied to Commit #3's LLMAgentStrategyOutcome history
    instead of memory feedback -- the two evidence shapes differ enough
    (outcomes are a flat, append-only success/failure history; memory
    quality also folds in categorical feedback and consolidation) that
    reusing that assessor's code directly would mean bending it around a
    shape it was never given, so the formula is re-expressed here rather
    than imported, but the shape (a bounded [0.0, 1.0] score, a separate
    bounded confidence, an evidence_count, and a human-readable reason)
    is the exact one that module -- and
    backend.agent_memory_relevance_scoring.LLMAgentMemoryRelevanceScorer
    before it -- already established for this repository.

    score()/score_many() are pure functions of a strategy's current
    outcome history and `now`: neither ever calls
    LLMAgentStrategyService.update()/archive() or
    LLMAgentStrategyOutcomeService.record() -- scoring a strategy can
    never mutate it or its evidence, and nothing computed here is stored.
    Called twice with the same evidence and the same `now`, both always
    return the same result.

    score is a recency-weighted success rate: each outcome contributes
    1.0 (SUCCEEDED) or 0.0 (FAILED), weighted by how long ago it was
    recorded, so a strategy's most recent performance dominates the
    number without a single old outcome (successful or not) ever pinning
    it forever. confidence is entirely separate, and is what actually
    enforces "do not treat a strategy as highly reliable on thin
    evidence": it grows with evidence_count (one lone outcome -- success
    or failure -- can drive score to either extreme, but never earns more
    than modest confidence) and shrinks when outcomes disagree with each
    other (an agreement factor -- contradictory outcomes are never
    dropped or averaged away silently; they are exactly what pulls
    confidence down, while still counting fully toward score itself).
    """

    def __init__(
        self,
        strategy_service: LLMAgentStrategyService,
        outcome_service: LLMAgentStrategyOutcomeService,
    ):
        self._strategy_service = strategy_service
        self._outcome_service = outcome_service

    def score(self, strategy_id: str, now: datetime = None) -> LLMAgentStrategyScore:
        """Score one strategy from its currently available Commit #3 outcome evidence.

        Raises:
            UnknownAgentStrategyError: If strategy_id was never created by
                Commit #1 (propagated, not wrapped)
        """
        self._strategy_service.get(strategy_id)
        outcomes = self._outcome_service.list_for_strategy(strategy_id)
        now = now or datetime.now(timezone.utc)

        if not outcomes:
            return LLMAgentStrategyScore(
                strategy_id=strategy_id,
                score=_BASELINE_SCORE,
                confidence=0.0,
                evidence_count=0,
                succeeded_count=0,
                failed_count=0,
                reason="no outcomes recorded yet; neutral baseline at zero confidence",
                scored_at=now,
            )

        succeeded_count = sum(1 for outcome in outcomes if outcome.result == SUCCEEDED)
        failed_count = len(outcomes) - succeeded_count
        evidence_count = len(outcomes)

        weights = [_recency_weight(outcome, now) for outcome in outcomes]
        weighted_success = sum(
            weight * (1.0 if outcome.result == SUCCEEDED else 0.0)
            for weight, outcome in zip(weights, outcomes)
        )
        total_weight = sum(weights)
        score = round(weighted_success / total_weight, 6)

        # Evidence volume: approaches 1.0 as outcomes accumulate, but a
        # single outcome (evidence_count == 1) caps confidence at 0.5,
        # whatever score it produced on its own.
        evidence_confidence = 1.0 - 0.5 ** evidence_count

        # Agreement: what share of outcomes falls on the majority side --
        # 1.0 when every outcome agrees (all succeeded or all failed), as
        # low as 0.5 when evenly split between success and failure.
        agreement_factor = max(succeeded_count, failed_count) / evidence_count

        confidence = round(evidence_confidence * agreement_factor, 6)

        reason = (
            f"{evidence_count} outcome(s): {succeeded_count} succeeded, {failed_count} failed; "
            f"recency-weighted score={score:.3f}; evidence_confidence={evidence_confidence:.3f}; "
            f"agreement={agreement_factor:.3f}"
        )

        return LLMAgentStrategyScore(
            strategy_id=strategy_id,
            score=score,
            confidence=confidence,
            evidence_count=evidence_count,
            succeeded_count=succeeded_count,
            failed_count=failed_count,
            reason=reason,
            scored_at=now,
        )

    def score_many(self, strategy_ids: list, now: datetime = None) -> list:
        """score() every strategy_id, all judged as of the same `now` --
        so a batch reflects one consistent point in time rather than
        drifting recency as the loop runs."""
        now = now or datetime.now(timezone.utc)
        return [self.score(strategy_id, now=now) for strategy_id in strategy_ids]
