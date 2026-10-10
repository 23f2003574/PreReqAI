from datetime import timedelta

import pytest

from backend.agent_task_lifecycle import PLANNED, READY, RUNNING, LLMAgentTaskLifecycleService
from backend.agent_task_queue import InvalidQueueEntryError, LLMAgentTaskQueueService
from backend.agent_task_queue_reservation import LLMAgentTaskQueueReservationService
from backend.agent_task_queue_selection import LLMAgentTaskQueueSelectionService
from backend.agent_task_readiness import LLMAgentTaskReadinessService


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _services(reservation_default_ttl=None):
    lifecycle_service = LLMAgentTaskLifecycleService()
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)
    queue_service = LLMAgentTaskQueueService(readiness_service)
    reservation_service = LLMAgentTaskQueueReservationService(queue_service, default_ttl=reservation_default_ttl)
    selection_service = LLMAgentTaskQueueSelectionService(queue_service, readiness_service, reservation_service)
    return lifecycle_service, readiness_service, queue_service, reservation_service, selection_service


def _ready_task(lifecycle_service, **overrides):
    task = lifecycle_service.create(_definition(**overrides))
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    return task


class TestSelectsHighestPriority:
    def test_select_next_returns_highest_priority_ready_task(self):
        lifecycle_service, _, queue_service, _, selection_service = _services()
        low = _ready_task(lifecycle_service)
        high = _ready_task(lifecycle_service)
        queue_service.enqueue(low.task_id, priority=1)
        queue_service.enqueue(high.task_id, priority=10)

        selected = selection_service.select_next()

        assert len(selected) == 1
        assert selected[0].task_id == high.task_id

    def test_select_returns_entry_for_selectable_task(self):
        lifecycle_service, _, queue_service, _, selection_service = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)

        selected = selection_service.select(task.task_id)

        assert selected is not None
        assert selected.task_id == task.task_id


class TestSkipsNonReady:
    def test_select_next_excludes_task_that_became_not_ready(self):
        lifecycle_service, _, queue_service, _, selection_service = _services()
        stale = _ready_task(lifecycle_service)
        fresh = _ready_task(lifecycle_service)
        queue_service.enqueue(stale.task_id, priority=100)
        queue_service.enqueue(fresh.task_id, priority=1)
        lifecycle_service.transition(stale.task_id, RUNNING)

        selected = selection_service.select_next(limit=10)

        assert [entry.task_id for entry in selected] == [fresh.task_id]

    def test_select_returns_none_for_non_ready_task(self):
        lifecycle_service, _, queue_service, _, selection_service = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)
        lifecycle_service.transition(task.task_id, RUNNING)

        assert selection_service.select(task.task_id) is None


class TestSkipsReserved:
    def test_select_next_excludes_actively_reserved_task(self):
        lifecycle_service, _, queue_service, reservation_service, selection_service = _services()
        reserved = _ready_task(lifecycle_service)
        free = _ready_task(lifecycle_service)
        queue_service.enqueue(reserved.task_id, priority=100)
        queue_service.enqueue(free.task_id, priority=1)
        reservation_service.reserve(reserved.task_id, "worker-1")

        selected = selection_service.select_next(limit=10)

        assert [entry.task_id for entry in selected] == [free.task_id]

    def test_select_returns_none_for_reserved_task(self):
        lifecycle_service, _, queue_service, reservation_service, selection_service = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)
        reservation_service.reserve(task.task_id, "worker-1")

        assert selection_service.select(task.task_id) is None

    def test_expired_reservation_does_not_block_selection(self):
        lifecycle_service, _, queue_service, reservation_service, selection_service = _services(
            reservation_default_ttl=timedelta(seconds=-1)
        )
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)
        reservation_service.reserve(task.task_id, "worker-1")

        assert selection_service.select(task.task_id) is not None


class TestMultiItemSelection:
    def test_select_next_returns_up_to_limit_in_order(self):
        lifecycle_service, _, queue_service, _, selection_service = _services()
        tasks = []
        for priority in (5, 20, 1, 15):
            task = _ready_task(lifecycle_service)
            queue_service.enqueue(task.task_id, priority=priority)
            tasks.append((priority, task.task_id))

        selected = selection_service.select_next(limit=2)

        ranked = sorted(tasks, key=lambda pair: -pair[0])
        assert [entry.task_id for entry in selected] == [task_id for _, task_id in ranked[:2]]

    def test_select_next_limit_zero_returns_empty(self):
        lifecycle_service, _, queue_service, _, selection_service = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)

        assert selection_service.select_next(limit=0) == []

    def test_select_next_invalid_limit_raises(self):
        _, _, _, _, selection_service = _services()
        with pytest.raises(InvalidQueueEntryError):
            selection_service.select_next(limit=-1)
        with pytest.raises(InvalidQueueEntryError):
            selection_service.select_next(limit="two")


class TestEmptyQueue:
    def test_select_next_empty_queue_returns_empty_list(self):
        _, _, _, _, selection_service = _services()
        assert selection_service.select_next() == []

    def test_select_missing_task_returns_none(self):
        _, _, _, _, selection_service = _services()
        assert selection_service.select("no-such-task") is None


class TestStaleOrMissing:
    def test_select_never_created_task_returns_none(self):
        _, _, _, _, selection_service = _services()
        assert selection_service.select("phantom-task") is None

    def test_select_requires_task_id(self):
        _, _, _, _, selection_service = _services()
        with pytest.raises(InvalidQueueEntryError):
            selection_service.select("")


class TestReadOnly:
    def test_select_next_does_not_mutate_queue_or_reservations(self):
        lifecycle_service, _, queue_service, reservation_service, selection_service = _services()
        task = _ready_task(lifecycle_service)
        entry_before = queue_service.enqueue(task.task_id, priority=7)

        selection_service.select_next(limit=5)
        selection_service.select(task.task_id)

        entry_after = queue_service.store.get(task.task_id)
        assert entry_after == entry_before
        assert reservation_service.get_reservation(task.task_id) is None

    def test_repeated_selection_is_deterministic(self):
        lifecycle_service, _, queue_service, _, selection_service = _services()
        for priority in (3, 9, 1):
            task = _ready_task(lifecycle_service)
            queue_service.enqueue(task.task_id, priority=priority)

        first = [e.task_id for e in selection_service.select_next(limit=10)]
        second = [e.task_id for e in selection_service.select_next(limit=10)]
        assert first == second
