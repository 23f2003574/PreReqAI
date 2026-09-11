import pytest

from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_lifecycle import (
    COMPLETED,
    PLANNED,
    READY,
    RUNNING,
    LLMAgentTaskLifecycleService,
)
from backend.agent_task_queue import InvalidQueueEntryError, LLMAgentTaskQueueService
from backend.agent_task_queue_rebalancer import LLMAgentTaskQueueRebalancer
from backend.agent_task_queue_reservation import LLMAgentTaskQueueReservationService
from backend.agent_task_readiness import LLMAgentTaskReadinessService


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _services(with_dependencies=False):
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service) if with_dependencies else None
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service, dependency_service=dependency_service)
    queue_service = LLMAgentTaskQueueService(readiness_service)
    reservation_service = LLMAgentTaskQueueReservationService(queue_service)
    rebalancer = LLMAgentTaskQueueRebalancer(queue_service, readiness_service, reservation_service)
    return lifecycle_service, dependency_service, readiness_service, queue_service, reservation_service, rebalancer


def _ready_task(lifecycle_service, **overrides):
    task = lifecycle_service.create(_definition(**overrides))
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    return task


def _complete_task(lifecycle_service, task_id):
    lifecycle_service.transition(task_id, RUNNING)
    lifecycle_service.transition(task_id, COMPLETED)


class TestNoOpRebalance:
    def test_no_op_rebalance_leaves_queue_unchanged(self):
        lifecycle_service, _, _, queue_service, _, rebalancer = _services()
        a = _ready_task(lifecycle_service)
        b = _ready_task(lifecycle_service)
        queue_service.enqueue(a.task_id, priority=5)
        queue_service.enqueue(b.task_id, priority=1)

        result = rebalancer.rebalance()

        assert result.removed_tasks == []
        assert result.reordered_tasks == []
        assert set(result.unchanged_tasks) == {a.task_id, b.task_id}
        assert set(result.affected_tasks) == {a.task_id, b.task_id}
        assert queue_service.contains(a.task_id)
        assert queue_service.contains(b.task_id)


class TestIneligibleTaskHandling:
    def test_ineligible_unreserved_task_is_removed(self):
        lifecycle_service, _, _, queue_service, _, rebalancer = _services()
        stale = _ready_task(lifecycle_service)
        fresh = _ready_task(lifecycle_service)
        queue_service.enqueue(stale.task_id, priority=100)
        queue_service.enqueue(fresh.task_id, priority=1)
        lifecycle_service.transition(stale.task_id, RUNNING)  # now not-ready

        result = rebalancer.rebalance()

        assert result.removed_tasks == [stale.task_id]
        assert fresh.task_id in result.unchanged_tasks
        assert not queue_service.contains(stale.task_id)
        assert queue_service.contains(fresh.task_id)

    def test_task_ids_referencing_unqueued_task_is_ignored(self):
        lifecycle_service, _, _, queue_service, _, rebalancer = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)

        result = rebalancer.rebalance(task_ids=[task.task_id, "phantom-task"])

        assert result.affected_tasks == [task.task_id]
        assert result.removed_tasks == []
        assert "phantom-task" not in (
            result.affected_tasks + result.removed_tasks + result.reordered_tasks + result.unchanged_tasks
        )

    def test_rebalance_rejects_non_list_task_ids(self):
        _, _, _, _, _, rebalancer = _services()
        with pytest.raises(InvalidQueueEntryError):
            rebalancer.rebalance(task_ids="not-a-list")


class TestReservedTaskProtected:
    def test_reserved_ineligible_task_is_not_removed(self):
        lifecycle_service, _, _, queue_service, reservation_service, rebalancer = _services()
        reserved = _ready_task(lifecycle_service)
        other = _ready_task(lifecycle_service)
        queue_service.enqueue(reserved.task_id, priority=50)
        queue_service.enqueue(other.task_id, priority=1)
        reservation_service.reserve(reserved.task_id, "worker-1")
        lifecycle_service.transition(reserved.task_id, RUNNING)  # now not-ready, but reserved

        result = rebalancer.rebalance()

        assert result.removed_tasks == []
        assert reserved.task_id in result.unchanged_tasks
        assert queue_service.contains(reserved.task_id)
        assert reservation_service.is_reservation_valid(reserved.task_id)


class TestMultipleTasksReorderDeterministically:
    def test_readiness_change_reorders_survivors(self):
        (
            lifecycle_service,
            dependency_service,
            readiness_service,
            queue_service,
            reservation_service,
            rebalancer,
        ) = _services(with_dependencies=True)

        blocked = _ready_task(lifecycle_service)  # will be reserved + blocked, high priority
        prerequisite = _ready_task(lifecycle_service)
        other = _ready_task(lifecycle_service)  # stays ready throughout, low priority

        queue_service.enqueue(blocked.task_id, priority=10)
        queue_service.enqueue(other.task_id, priority=1)

        # Protect `blocked` before making it unready, so rebalance()
        # never removes it.
        reservation_service.reserve(blocked.task_id, "worker-1")
        dependency_service.add_dependency(blocked.task_id, prerequisite.task_id)
        assert readiness_service.is_ready(blocked.task_id) is False

        first = rebalancer.rebalance(task_ids=[blocked.task_id, other.task_id])
        assert first.removed_tasks == []
        # First observation: nothing to compare against yet.
        assert set(first.unchanged_tasks) == {blocked.task_id, other.task_id}
        assert first.reordered_tasks == []

        # Satisfy the dependency -- `blocked` becomes ready again,
        # while remaining queued the whole time (protected throughout).
        _complete_task(lifecycle_service, prerequisite.task_id)
        assert readiness_service.is_ready(blocked.task_id) is True

        second = rebalancer.rebalance(task_ids=[blocked.task_id, other.task_id])
        assert second.removed_tasks == []
        assert set(second.reordered_tasks) == {blocked.task_id, other.task_id}
        assert second.unchanged_tasks == []

        # Final order reflects blocked's higher priority now that both
        # are ready.
        ordered = [entry.task_id for entry in queue_service.peek()]
        assert ordered.index(blocked.task_id) < ordered.index(other.task_id)


class TestRepeatedRebalanceIdempotent:
    def test_repeated_rebalance_produces_no_additional_changes(self):
        lifecycle_service, _, _, queue_service, _, rebalancer = _services()
        a = _ready_task(lifecycle_service)
        b = _ready_task(lifecycle_service)
        queue_service.enqueue(a.task_id, priority=5)
        queue_service.enqueue(b.task_id, priority=1)

        first = rebalancer.rebalance()
        second = rebalancer.rebalance()

        assert first.removed_tasks == second.removed_tasks == []
        assert first.reordered_tasks == second.reordered_tasks == []
        assert set(second.unchanged_tasks) == {a.task_id, b.task_id}

    def test_repeated_rebalance_after_removal_is_stable(self):
        lifecycle_service, _, _, queue_service, _, rebalancer = _services()
        stale = _ready_task(lifecycle_service)
        fresh = _ready_task(lifecycle_service)
        queue_service.enqueue(stale.task_id, priority=100)
        queue_service.enqueue(fresh.task_id, priority=1)
        lifecycle_service.transition(stale.task_id, RUNNING)

        first = rebalancer.rebalance()
        second = rebalancer.rebalance()

        assert first.removed_tasks == [stale.task_id]
        assert second.removed_tasks == []
        assert second.affected_tasks == [fresh.task_id]
        assert second.unchanged_tasks == [fresh.task_id]


class TestScopedRebalance:
    def test_rebalance_scoped_to_given_task_ids_ignores_others(self):
        lifecycle_service, _, _, queue_service, _, rebalancer = _services()
        stale = _ready_task(lifecycle_service)
        other_stale = _ready_task(lifecycle_service)
        queue_service.enqueue(stale.task_id)
        queue_service.enqueue(other_stale.task_id)
        lifecycle_service.transition(stale.task_id, RUNNING)
        lifecycle_service.transition(other_stale.task_id, RUNNING)

        result = rebalancer.rebalance(task_ids=[stale.task_id])

        assert result.removed_tasks == [stale.task_id]
        assert not queue_service.contains(stale.task_id)
        # other_stale was never part of this call's scope, so it is
        # left untouched even though it is equally ineligible.
        assert queue_service.contains(other_stale.task_id)
