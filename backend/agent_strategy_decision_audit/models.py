from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

# The kinds of strategy-driven planning choice this trail records.
# Deliberately small and closed, the same reasoning every other closed
# vocabulary in this series (VALID_MEMORY_TYPES, VALID_RESULTS, ...)
# already documents. LEARNED is Commit #12's own addition: the lifecycle
# verdict (Commit #9's own ACTIVE/TRUSTED/DEPRECATED) reached once an
# applied strategy's real execution outcome has been folded back into its
# effectiveness -- distinct from the four planning-time decisions above,
# all of which happen before any execution result exists to learn from.
SELECTED = "selected"
REJECTED = "rejected"
CONFLICT_RESOLVED = "conflict_resolved"
APPLIED = "applied"
LEARNED = "learned"
DECISION_TYPES = frozenset({SELECTED, REJECTED, CONFLICT_RESOLVED, APPLIED, LEARNED})


@dataclass(frozen=True)
class LLMAgentStrategyDecision:
    """One immutable snapshot of a strategy-driven planning choice --
    Commit #5's own selection, Commit #10's own conflict resolution, or
    Commit #6's own application -- made observable after the fact.

    execution_or_task_id names whatever identifier was actually available
    when the decision was made: Commit #5/#6/#10 all run before a plan is
    ever executed, so most decisions carry a caller-supplied task
    identifier rather than a real Commit #12 execution_id; once an
    execution exists, the same field can carry that instead. Either way
    it is never fabricated by this module -- it is always exactly what
    the caller recording the decision was given.

    decision_type is one of DECISION_TYPES; decision is the concrete,
    short verdict within that type (e.g. "included"/"excluded" for
    SELECTED, "won"/"lost"/"unresolved" for CONFLICT_RESOLVED). score and
    evidence are whatever quantitative/structured backing Commit #4/#5/#10
    already computed for this decision, carried through unchanged rather
    than re-derived -- reason is that same source's own human-readable
    explanation, verbatim.

    Never updated or deleted once recorded -- record() only ever appends
    a new LLMAgentStrategyDecision, the same append-only history
    discipline backend.agent_strategy_effectiveness.LLMAgentStrategyOutcome
    and backend.agent_strategy_usage.LLMAgentStrategyUsage already
    establish for this series. Recording a decision never mutates the
    strategy, selection, or conflict resolution it observes -- this
    module only ever reads what Commit #5/#6/#10 already produced.
    """

    strategy_id: str
    execution_or_task_id: str
    decision_type: str
    decision: str
    reason: str
    score: Optional[float] = None
    evidence: Any = field(default_factory=dict)
    decision_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentStrategyDecision":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)
