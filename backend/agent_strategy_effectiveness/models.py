from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from backend.llm.tool_execution import FAILED, SUCCEEDED

# result is never taken on the caller's word -- record() derives it from
# the originating execution's own verified terminal status, the exact
# discipline backend.agent_execution_memory.VALID_OUTCOMES documents, so
# only these two ever reach storage.
VALID_RESULTS = frozenset({SUCCEEDED, FAILED})


@dataclass(frozen=True)
class LLMAgentStrategyOutcome:
    """One explicit record of how a Commit #1 strategy actually performed
    when a real execution used it.

    Links every outcome to both strategy_id and execution_id, always --
    neither is ever optional, so an outcome is never ambiguous about which
    strategy it is evidence for or which execution it came from. result
    mirrors backend.agent_execution_memory.LLMAgentMemory.outcome's own
    provenance discipline: it is never a caller's claim, only ever the
    originating execution's own verified terminal status.

    evidence is deliberately minimal, caller-supplied outcome metadata
    (e.g. a short note on what happened) -- never raw execution internals
    (step arguments, tool output, full traces). Nothing here copies the
    execution's own record into evidence automatically; a caller who wants
    execution detail already has execution_id to look it up through the
    real LLMAgentPlanExecutionService.

    Never updated or deleted once recorded -- record() only ever appends
    a new LLMAgentStrategyOutcome (or, for a (strategy_id, execution_id)
    pair already on record, returns the existing one unchanged), the same
    append-only, idempotent-by-pair discipline preserving history the way
    backend.agent_memory_feedback.LLMAgentMemoryFeedback already does for
    memory feedback.
    """

    strategy_id: str
    execution_id: str
    result: str
    evidence: Any = field(default_factory=dict)
    outcome_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentStrategyOutcome":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)


@dataclass(frozen=True)
class LLMAgentStrategyEffectiveness:
    """One point-in-time aggregate of every outcome on record for a
    Commit #1 strategy -- a summary, never a stored or persisted verdict:
    summarize() recomputes this fresh from LLMAgentStrategyOutcomeService.
    list_for_strategy() every time it is called, so it always reflects
    every outcome recorded up to that call, and nothing here feeds back
    into the strategy's own status or ranking (no automatic lifecycle or
    ranking decision is made from it yet).
    """

    strategy_id: str
    total_outcomes: int
    succeeded_count: int
    failed_count: int
    success_rate: float
    last_outcome_at: Optional[datetime]
