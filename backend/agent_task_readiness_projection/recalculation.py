from backend.agent_task_dependency_readiness_cache import LLMAgentTaskDependencyReadinessCache
from backend.agent_task_dependency_readiness_recalculation import AgentTaskReadinessRecalculationResult

from .service import LLMAgentTaskReadinessProjectionService


def project_recalculation(
    projection_service: LLMAgentTaskReadinessProjectionService,
    cache: LLMAgentTaskDependencyReadinessCache,
    recalculation_result: AgentTaskReadinessRecalculationResult,
) -> list:
    """Bridges Commit #12's own
    LLMAgentTaskDependencyReadinessRecalculator.recalculate() output
    into this module's own project() -- Rule: "reuse Commit #12
    recalculation output."

    For every task_id recalculate() actually succeeded for
    (recalculation_result.recalculated_tasks), reads the fresh Commit
    #8 plan Commit #12 itself just wrote via Commit #9's own
    cache.set() -- guaranteed to be a live, non-stale hit here, since it
    was cached moments earlier by the exact same recalculate() call
    this function's own result came from -- and projects it. A task_id
    in recalculation_result.failed_recalculations is never projected:
    Commit #12 itself never cached anything for it either (Rule:
    "preserve cache correctness if recalculation fails"), so there is
    nothing valid here to project either.

    A pure bridge, nothing more: never calls recalculate() itself, never
    reads or writes Commit #1/#5's own state, and never mutates the
    cache -- only cache.get() (read) and project() (this module's own
    single write) are ever called (Rule: "no execution, scheduling, or
    mutation of task/dependency state").
    """
    projections = []
    for task_id in recalculation_result.recalculated_tasks:
        plan = cache.get(task_id)
        if plan is None:
            continue
        projections.append(projection_service.project(task_id, plan))
    return projections
