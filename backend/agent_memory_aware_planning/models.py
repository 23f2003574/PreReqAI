from dataclasses import dataclass

from backend.agent_task_planning import LLMAgentPlan


@dataclass(frozen=True)
class LLMAgentMemoryPlanningContext:
    """The memory-derived input available to one planning call, kept
    entirely separate from whatever plan the model actually produces from
    it.

    applicable_memories is Commit #10's own prepare() output for this
    scope_id/task -- already scope-isolated, deduplicated after
    consolidation, trust-preferred, and limited; nothing here re-derives
    or re-filters it a second way. memory_evidence splits that same list
    by each memory's own (Commit #1-verified) outcome into
    "proven_strategies" (SUCCEEDED) and "known_failure_patterns" (FAILED)
    -- both are always present, even when one is empty, so a caller (or
    the model reading it) can see both proven approaches and known
    pitfalls side by side rather than only whichever happened to rank
    first. memory_provenance is one entry per applicable memory --
    memory_id, execution_id, status, relevance_score -- so every
    memory-derived recommendation stays traceable back to the record and
    execution it came from.
    """

    scope_id: str
    task: str
    applicable_memories: list
    memory_evidence: dict
    memory_provenance: list


@dataclass(frozen=True)
class LLMAgentMemoryAwarePlan:
    """One planning call's result, keeping the newly generated plan
    distinct from the memory evidence that informed it.

    plan is exactly backend.agent_task_planning.LLMAgentPlanningService's
    own LLMAgentPlan -- produced by the real, unmodified planner, never a
    second planning implementation. memory_context is the
    LLMAgentMemoryPlanningContext that was applied before create() was
    called. Nothing here merges the two into one structure: a
    memory-derived recommendation is never indistinguishable from a
    decision the model generated on its own.
    """

    plan: LLMAgentPlan
    memory_context: LLMAgentMemoryPlanningContext
