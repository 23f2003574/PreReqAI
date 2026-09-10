import pytest

from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_impact import LLMAgentTaskDependencyImpactService
from backend.agent_task_dependency_readiness_cache import LLMAgentTaskDependencyReadinessCache
from backend.agent_task_dependency_readiness_plan import (
    AgentTaskDependencyReadinessPlan,
    LLMAgentTaskDependencyReadinessService,
)
from backend.agent_task_dependency_readiness_recalculation import LLMAgentTaskDependencyReadinessRecalculator
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import PLANNED, READY, RUNNING, LLMAgentTaskLifecycleService
from backend.agent_task_readiness_projection import (
    AgentTaskReadinessProjection,
    InvalidReadinessProjectionError,
    JsonAgentTaskReadinessProjectionStore,
    LLMAgentTaskReadinessProjectionService,
    project_recalculation,
)


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _new_task(lifecycle_service, **overrides):
    return lifecycle_service.create(_definition(**overrides))


def _advance_to(lifecycle_service, task, state):
    for target in (PLANNED, READY, RUNNING):
        if task.current_state == state:
            return task
        task = lifecycle_service.transition(task.task_id, target)
    return lifecycle_service.transition(task.task_id, state) if task.current_state != state else task


def _services():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    readiness_plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    projection_service = LLMAgentTaskReadinessProjectionService(lifecycle_service)
    return lifecycle_service, dependency_service, readiness_plan_service, projection_service


# --- project + retrieve latest readiness --------------------------------------------------------


def test_project_and_retrieve_latest_readiness():
    lifecycle_service, dependency_service, readiness_plan_service, projection_service = _services()
    task = _new_task(lifecycle_service)
    plan = readiness_plan_service.build_plan(task.task_id)

    projected = projection_service.project(task.task_id, plan)

    assert isinstance(projected, AgentTaskReadinessProjection)
    assert projected.task_id == task.task_id
    assert projected.ready is True

    fetched = projection_service.get(task.task_id)
    assert fetched == projected


def test_get_missing_projection_returns_none():
    lifecycle_service, dependency_service, readiness_plan_service, projection_service = _services()
    task = _new_task(lifecycle_service)

    assert projection_service.get(task.task_id) is None


def test_project_rejects_mismatched_readiness_result():
    lifecycle_service, dependency_service, readiness_plan_service, projection_service = _services()
    task_a = _new_task(lifecycle_service)
    task_b = _new_task(lifecycle_service)
    plan_b = readiness_plan_service.build_plan(task_b.task_id)

    with pytest.raises(InvalidReadinessProjectionError):
        projection_service.project(task_a.task_id, plan_b)


def test_project_rejects_wrong_result_type():
    lifecycle_service, dependency_service, readiness_plan_service, projection_service = _services()
    task = _new_task(lifecycle_service)

    with pytest.raises(InvalidReadinessProjectionError):
        projection_service.project(task.task_id, {"ready": True})


# --- re-project replaces current projection correctly ------------------------------------------


def test_reproject_replaces_current_projection():
    lifecycle_service, dependency_service, readiness_plan_service, projection_service = _services()
    task = _new_task(lifecycle_service)
    dep = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)

    first_plan = readiness_plan_service.build_plan(task.task_id)
    first_projection = projection_service.project(task.task_id, first_plan)
    assert first_projection.ready is False

    dependency_service.remove_dependency(task.task_id, dep.task_id)
    second_plan = readiness_plan_service.build_plan(task.task_id)
    second_projection = projection_service.project(task.task_id, second_plan)

    assert second_projection.ready is True
    fetched = projection_service.get(task.task_id)
    assert fetched.ready is True
    assert fetched.projection_id == second_projection.projection_id  # first was replaced, not kept


# --- stale projection detected --------------------------------------------------------------------


def test_stale_projection_detected_and_not_returned():
    lifecycle_service, dependency_service, readiness_plan_service, projection_service = _services()
    task = _new_task(lifecycle_service)
    plan = readiness_plan_service.build_plan(task.task_id)
    projection_service.project(task.task_id, plan)
    assert projection_service.get(task.task_id) is not None

    lifecycle_service.transition(task.task_id, PLANNED)  # bumps task's own updated_at

    assert projection_service.get(task.task_id) is None


def test_fresh_projection_is_not_considered_stale():
    lifecycle_service, dependency_service, readiness_plan_service, projection_service = _services()
    task = _new_task(lifecycle_service)
    plan = readiness_plan_service.build_plan(task.task_id)

    projection_service.project(task.task_id, plan)

    assert projection_service.get(task.task_id) is not None


# --- blocking/pending/failed dependency data preserved ------------------------------------------


def test_blocking_pending_failed_dependency_data_preserved():
    lifecycle_service, dependency_service, readiness_plan_service, projection_service = _services()
    task = _new_task(lifecycle_service)
    pending_dep = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, pending_dep.task_id)

    plan = readiness_plan_service.build_plan(task.task_id)
    projected = projection_service.project(task.task_id, plan)

    assert projected.ready is False
    assert projected.pending_dependencies == list(plan.pending_tasks)
    assert projected.failed_dependencies == list(plan.failed_tasks)
    assert any(pending_dep.task_id in reason for reason in projected.blocking_reasons)


# --- multiple tasks remain isolated -----------------------------------------------------------------


def test_multiple_tasks_remain_isolated():
    lifecycle_service, dependency_service, readiness_plan_service, projection_service = _services()
    task_a = _new_task(lifecycle_service)
    task_b = _new_task(lifecycle_service)
    dep_b = _new_task(lifecycle_service)
    dependency_service.add_dependency(task_b.task_id, dep_b.task_id)

    projection_service.project(task_a.task_id, readiness_plan_service.build_plan(task_a.task_id))
    projection_service.project(task_b.task_id, readiness_plan_service.build_plan(task_b.task_id))

    projection_a = projection_service.get(task_a.task_id)
    projection_b = projection_service.get(task_b.task_id)
    assert projection_a.ready is True
    assert projection_b.ready is False
    assert projection_a.task_id != projection_b.task_id


def test_list_affected_returns_only_requested_valid_projections():
    lifecycle_service, dependency_service, readiness_plan_service, projection_service = _services()
    task_a = _new_task(lifecycle_service)
    task_b = _new_task(lifecycle_service)
    task_c = _new_task(lifecycle_service)  # never projected
    projection_service.project(task_a.task_id, readiness_plan_service.build_plan(task_a.task_id))
    projection_service.project(task_b.task_id, readiness_plan_service.build_plan(task_b.task_id))

    results = projection_service.list_affected([task_a.task_id, task_b.task_id, task_c.task_id])

    assert {projection.task_id for projection in results} == {task_a.task_id, task_b.task_id}


def test_list_affected_rejects_non_list():
    lifecycle_service, dependency_service, readiness_plan_service, projection_service = _services()

    with pytest.raises(InvalidReadinessProjectionError):
        projection_service.list_affected("not-a-list")


# --- repeated identical projection is idempotent -------------------------------------------------


def test_repeated_identical_projection_is_idempotent():
    lifecycle_service, dependency_service, readiness_plan_service, projection_service = _services()
    task = _new_task(lifecycle_service)
    plan = readiness_plan_service.build_plan(task.task_id)

    first = projection_service.project(task.task_id, plan)
    second = projection_service.project(task.task_id, plan)

    assert first.task_id == second.task_id
    assert first.ready == second.ready
    assert first.blocking_reasons == second.blocking_reasons
    assert first.pending_dependencies == second.pending_dependencies
    assert first.failed_dependencies == second.failed_dependencies
    assert first.source_version == second.source_version
    # Store bookkeeping (identity/timestamp) is free to move, same as
    # every other *Store.save() in this series -- only one entry exists.
    assert projection_service.get(task.task_id).projection_id == second.projection_id


# --- JSON persistence --------------------------------------------------------------------------------


def test_json_store_round_trips_across_service_instances(tmp_path):
    path = tmp_path / "projections.json"
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    readiness_plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    task = _new_task(lifecycle_service)

    service_a = LLMAgentTaskReadinessProjectionService(
        lifecycle_service, store=JsonAgentTaskReadinessProjectionStore(path)
    )
    service_a.project(task.task_id, readiness_plan_service.build_plan(task.task_id))

    service_b = LLMAgentTaskReadinessProjectionService(
        lifecycle_service, store=JsonAgentTaskReadinessProjectionStore(path)
    )
    fetched = service_b.get(task.task_id)

    assert fetched is not None
    assert fetched.ready is True


# --- Commit #12 integration bridge ------------------------------------------------------------------


def test_project_recalculation_bridges_commit_12_output():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    dependency_impact_service = LLMAgentTaskDependencyImpactService(lifecycle_service, dependency_service, resolver)
    readiness_plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    cache = LLMAgentTaskDependencyReadinessCache(lifecycle_service, dependency_service)
    recalculator = LLMAgentTaskDependencyReadinessRecalculator(dependency_impact_service, readiness_plan_service, cache)
    projection_service = LLMAgentTaskReadinessProjectionService(lifecycle_service)

    task = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, task.task_id)

    result = recalculator.recalculate(task.task_id)
    projections = project_recalculation(projection_service, cache, result)

    assert {projection.task_id for projection in projections} == set(result.recalculated_tasks)
    assert projection_service.get(task.task_id) is not None
    assert projection_service.get(dependent.task_id) is not None


def test_project_recalculation_skips_failed_tasks():
    from backend.agent_task_dependencies import TaskDependency

    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    dependency_impact_service = LLMAgentTaskDependencyImpactService(lifecycle_service, dependency_service, resolver)
    readiness_plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    cache = LLMAgentTaskDependencyReadinessCache(lifecycle_service, dependency_service)
    recalculator = LLMAgentTaskDependencyReadinessRecalculator(dependency_impact_service, readiness_plan_service, cache)
    projection_service = LLMAgentTaskReadinessProjectionService(lifecycle_service)

    task = _new_task(lifecycle_service)
    dependency_service.store.save(TaskDependency(task_id="ghost-dependent", dependency_task_id=task.task_id))

    result = recalculator.recalculate(task.task_id)
    projections = project_recalculation(projection_service, cache, result)

    assert "ghost-dependent" not in {projection.task_id for projection in projections}
    assert projection_service.get("ghost-dependent") is None


# --- no mutation of underlying task/dependency state -------------------------------------------------


def test_projection_operations_do_not_mutate_task_state():
    lifecycle_service, dependency_service, readiness_plan_service, projection_service = _services()
    task = _new_task(lifecycle_service)
    plan = readiness_plan_service.build_plan(task.task_id)

    before = lifecycle_service.get(task.task_id)
    projection_service.project(task.task_id, plan)
    projection_service.get(task.task_id)
    projection_service.list_affected([task.task_id])
    after = lifecycle_service.get(task.task_id)

    assert before == after
