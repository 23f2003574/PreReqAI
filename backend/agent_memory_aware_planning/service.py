import dataclasses
from datetime import datetime

from backend.agent_memory_application import DEFAULT_LIMIT, LLMAgentMemoryApplicator
from backend.agent_task_planning import LLMAgentPlanningService
from backend.llm.tool_execution import FAILED, SUCCEEDED

from .models import LLMAgentMemoryAwarePlan, LLMAgentMemoryPlanningContext

# The context key this service adds, distinct from Commit #10's own
# CONTEXT_KEY ("agent_memories") -- this carries the richer,
# planning-specific shape (evidence grouped by proven/failed, plus an
# explicit provenance list); Commit #10's own flat shape is not
# duplicated here, and this service never sets Commit #10's key itself.
PLANNING_CONTEXT_KEY = "memory_planning_context"


def _build_planning_context(scope_id: str, task: str, memory_context: dict) -> LLMAgentMemoryPlanningContext:
    memories = memory_context["memories"]
    proven_strategies = [entry for entry in memories if entry["outcome"] == SUCCEEDED]
    known_failure_patterns = [entry for entry in memories if entry["outcome"] == FAILED]

    provenance = [
        {
            "memory_id": entry["memory_id"],
            "execution_id": entry["execution_id"],
            "status": entry["status"],
            "relevance_score": entry["relevance_score"],
        }
        for entry in memories
    ]

    return LLMAgentMemoryPlanningContext(
        scope_id=scope_id,
        task=task,
        applicable_memories=memories,
        memory_evidence={
            "proven_strategies": proven_strategies,
            "known_failure_patterns": known_failure_patterns,
        },
        memory_provenance=provenance,
    )


class LLMAgentMemoryAwarePlanningService:
    """Makes the real backend.agent_task_planning.LLMAgentPlanningService
    explicitly account for applicable Commit #1 memory when producing a plan.

    Not a new planner or a parallel planning framework: create() calls
    the real, unmodified LLMAgentPlanningService.create() -- the actual
    planning entry point -- for every plan it returns, and the tool
    validation, dependency checking, and LLM orchestration that service
    already does are entirely untouched. What this service adds is
    upstream of that call: Commit #10's own LLMAgentMemoryApplicator.
    prepare() (read-only -- no memory, feedback, or promotion record is
    ever written by planning) supplies the applicable memories, reshaped
    into an LLMAgentMemoryPlanningContext that groups them into
    proven_strategies/known_failure_patterns and carries their
    provenance, then merged into the same `context: dict` parameter
    LLMAgentPlanningService.create() already accepts, under its own
    namespaced key -- so the planner reads memory evidence exactly the
    way it already reads any other supporting context, no prompt-template
    change of its own.

    Memory only ever informs planning, never overrides it: `task` is
    passed to the real planner completely unchanged, and when
    prepare() finds nothing applicable, memory_evidence is simply two
    empty lists -- create() still calls through to the same planner the
    same way, so a scope/task with no memory behaves exactly as it did
    before this service existed. The returned LLMAgentMemoryAwarePlan
    keeps the newly generated `plan` and the memory-derived
    `memory_context` as two separate fields, never merged into one, so a
    memory-derived recommendation is never mistaken for a decision the
    model made on its own.
    """

    def __init__(self, planning_service: LLMAgentPlanningService, applicator: LLMAgentMemoryApplicator):
        self._planning_service = planning_service
        self._applicator = applicator

    def create(
        self,
        scope_id: str,
        task: str,
        context: dict = None,
        limit: int = DEFAULT_LIMIT,
        include_deprecated: bool = False,
        now: datetime = None,
    ) -> LLMAgentMemoryAwarePlan:
        """Plan `task`, with scope_id's applicable memory made explicit to
        the real planner.

        Raises whatever the real LLMAgentPlanningService.create() raises
        for a malformed model response or an invalid task/context -- this
        method adds no new failure mode of its own beyond
        LLMAgentMemoryApplicator.prepare()'s own limit validation.
        """
        memory_context = self._applicator.prepare(
            scope_id, task, limit=limit, include_deprecated=include_deprecated, now=now
        )
        planning_context = _build_planning_context(scope_id, task, memory_context)

        enriched_context = dict(context) if context else {}
        enriched_context[PLANNING_CONTEXT_KEY] = dataclasses.asdict(planning_context)

        plan = self._planning_service.create(task, enriched_context)
        return LLMAgentMemoryAwarePlan(plan=plan, memory_context=planning_context)
