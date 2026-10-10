from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from backend.agent_strategy_library import ACTIVE

# ACTIVE is Commit #1's own value, reused as-is: it is this evaluator's
# base/default tier, exactly the same "active" a strategy already carries
# the moment Commit #1 creates it. TRUSTED/DEPRECATED are new values this
# evaluator alone assigns, the same "add a trust tier on top, never touch
# the original status field" shape
# backend.agent_memory_promotion.CANDIDATE/TRUSTED/DEPRECATED already
# established for memories -- reused here rather than a second, unrelated
# lifecycle vocabulary. This is deliberately independent of Commit #1's
# own ACTIVE/ARCHIVED status: a strategy can be lifecycle-DEPRECATED while
# still Commit #1-ACTIVE (still retrievable), and archiving a strategy
# (Commit #1) never implies anything about its lifecycle tier here.
TRUSTED = "trusted"
DEPRECATED = "deprecated"
STATUSES = frozenset({ACTIVE, TRUSTED, DEPRECATED})

# On the same [0.0, 1.0] scale Commit #4's own LLMAgentStrategyScore
# already uses. Reused at the exact same values
# backend.agent_memory_promotion.MIN_TRUSTED_QUALITY/MIN_TRUSTED_CONFIDENCE
# already established for the analogous memory decision -- one
#"sufficiently proven" bar for this whole repository, not a
# strategy-specific reinterpretation of it.
MIN_TRUSTED_SCORE = 0.7
MIN_TRUSTED_CONFIDENCE = 0.7

# The mirror image of the trusted bar: a strategy this unreliable, backed
# by evidence this solid, is deprecated rather than merely left ACTIVE.
# confidence is gated at the same MIN_TRUSTED_CONFIDENCE bar in both
# directions -- exactly what makes "repeated failures" the trigger rather
# than one bad outcome: Commit #4's own confidence formula only clears
# 0.7 once there are at least two unanimous outcomes (or more, the less
# they agree with each other), so a single failure can never push a
# strategy to DEPRECATED on its own.
MAX_DEPRECATED_SCORE = 0.3


@dataclass(frozen=True)
class LLMAgentStrategyLifecycleDecision:
    """One deterministic, explainable lifecycle judgment for a Commit #1
    strategy, computed and appended by evaluate().

    previous_status is the strategy's own most recent lifecycle status
    before this decision (ACTIVE, by convention, if evaluate() has never
    run for it before); status is what this decision assigns. score/
    confidence/evidence_count/succeeded_count/failed_count are Commit #4's
    own LLMAgentStrategyScore this decision was computed from, carried
    through unchanged -- mixed or contradictory evidence is never
    collapsed away: succeeded_count and failed_count are both always
    present, so a strategy's disagreement with itself stays visible in
    every decision made about it. reason is a human-readable breakdown of
    which thresholds were or were not cleared, the same explainability
    convention backend.agent_memory_promotion.LLMAgentMemoryPromotionRecord
    and Commit #4's own LLMAgentStrategyScore.reason already establish.

    Never updated or deleted once recorded -- evaluate() only ever
    appends a new LLMAgentStrategyLifecycleDecision, the same append-only
    history discipline backend.agent_memory_promotion's own promotion
    records already use, so a strategy's complete lifecycle trail stays
    reachable rather than being collapsed to a single mutable field. The
    strategy itself (its Commit #1 record, and every Commit #3 outcome
    behind it) is never touched by any of this.
    """

    strategy_id: str
    previous_status: str
    status: str
    reason: str
    score: float
    confidence: float
    evidence_count: int
    succeeded_count: int
    failed_count: int
    decision_id: str = field(default_factory=lambda: str(uuid4()))
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["decided_at"] = self.decided_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentStrategyLifecycleDecision":
        payload = dict(data)
        value = payload.get("decided_at")
        if isinstance(value, str):
            payload["decided_at"] = datetime.fromisoformat(value)
        return cls(**payload)
