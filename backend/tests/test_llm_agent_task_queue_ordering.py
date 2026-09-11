from datetime import datetime, timezone

import pytest

from backend.agent_task_lifecycle import PLANNED, READY, RUNNING, LLMAgentTaskLifecycleService
from backend.agent_task_queue import InvalidQueueEntryError, LLMAgentTaskQueueService, QueueEntry
from backend.agent_task_queue_ordering import LLMAgentTaskQueueOrderingService
from backend.agent_task_readiness import LLMAgentTaskReadinessService


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _services():
    lifecycle_service = LLMAgentTaskLifecycleService()
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)
    queue_service = LLMAgentTaskQueueService(readiness_service)
    return lifecycle_service, readiness_service, queue_service


def _ready_task(lifecycle_service, **overrides):
    task = lifecycle_service.create(_definition(**overrides))
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    return task


class TestPriorityOrdering:
    def test_order_sorts_by_priority_descending(self):
        lifecycle_service, _, queue_service = _services()
        low = _ready_task(lifecycle_service)
        high = _ready_task(lifecycle_service)
        mid = _ready_task(lifecycle_service)
        queue_service.enqueue(low.task_id, priority=1)
        queue_service.enqueue(high.task_id, priority=10)
        queue_service.enqueue(mid.task_id, priority=5)

        ordering_service = LLMAgentTaskQueueOrderingService()
        ordered = ordering_service.order(queue_service.peek())

        assert [entry.task_id for entry in ordered] == [high.task_id, mid.task_id, low.task_id]

    def test_next_returns_highest_priority(self):
        lifecycle_service, _, queue_service = _services()
        low = _ready_task(lifecycle_service)
        high = _ready_task(lifecycle_service)
        queue_service.enqueue(low.task_id, priority=1)
        queue_service.enqueue(high.task_id, priority=10)

        ordering_service = LLMAgentTaskQueueOrderingService()
        entries = queue_service.peek()

        assert ordering_service.next(entries).task_id == high.task_id

    def test_compare_reflects_priority(self):
        lifecycle_service, _, queue_service = _services()
        low = _ready_task(lifecycle_service)
        high = _ready_task(lifecycle_service)
        low_entry = queue_service.enqueue(low.task_id, priority=1)
        high_entry = queue_service.enqueue(high.task_id, priority=10)

        ordering_service = LLMAgentTaskQueueOrderingService()

        assert ordering_service.compare(high_entry, low_entry) == -1
        assert ordering_service.compare(low_entry, high_entry) == 1
        assert ordering_service.compare(low_entry, low_entry) == 0


class TestTieBreaking:
    def test_equal_priority_breaks_by_queued_at_then_task_id(self):
        lifecycle_service, _, queue_service = _services()
        first = _ready_task(lifecycle_service)
        second = _ready_task(lifecycle_service)
        first_entry = queue_service.enqueue(first.task_id, priority=3)
        second_entry = queue_service.enqueue(second.task_id, priority=3)

        ordering_service = LLMAgentTaskQueueOrderingService()
        ordered = ordering_service.order([second_entry, first_entry])

        expected_first = (
            first_entry.task_id
            if first_entry.queued_at != second_entry.queued_at
            else min(first_entry.task_id, second_entry.task_id)
        )
        assert ordered[0].task_id == expected_first

    def test_equal_priority_and_queued_at_breaks_by_task_id(self):
        same_time = datetime.now(timezone.utc)
        entry_b = QueueEntry(task_id="task-b", priority=1, queued_at=same_time)
        entry_a = QueueEntry(task_id="task-a", priority=1, queued_at=same_time)

        ordering_service = LLMAgentTaskQueueOrderingService()
        ordered = ordering_service.order([entry_b, entry_a])

        assert [entry.task_id for entry in ordered] == ["task-a", "task-b"]


class TestReadinessHandling:
    def test_readiness_ranked_first_when_readiness_service_given(self):
        lifecycle_service, readiness_service, queue_service = _services()
        stale = _ready_task(lifecycle_service)
        fresh = _ready_task(lifecycle_service)
        queue_service.enqueue(stale.task_id, priority=100)
        queue_service.enqueue(fresh.task_id, priority=1)

        # stale is no longer ready -- it already entered RUNNING, so
        # is_ready() (lifecycle_state check) now reports False, even
        # though it is still sitting in the queue (Commit #1 never
        # auto-evicts on a readiness change).
        lifecycle_service.transition(stale.task_id, RUNNING)

        ordering_service = LLMAgentTaskQueueOrderingService(readiness_service)
        entries = [
            e for e in [queue_service.store.get(stale.task_id), queue_service.store.get(fresh.task_id)]
        ]
        ordered = ordering_service.order(entries)

        assert ordered[0].task_id == fresh.task_id
        assert ordered[1].task_id == stale.task_id

    def test_readiness_ignored_without_readiness_service(self):
        lifecycle_service, readiness_service, queue_service = _services()
        stale = _ready_task(lifecycle_service)
        fresh = _ready_task(lifecycle_service)
        queue_service.enqueue(stale.task_id, priority=100)
        queue_service.enqueue(fresh.task_id, priority=1)
        lifecycle_service.transition(stale.task_id, RUNNING)

        ordering_service = LLMAgentTaskQueueOrderingService()  # no readiness_service
        entries = [queue_service.store.get(stale.task_id), queue_service.store.get(fresh.task_id)]
        ordered = ordering_service.order(entries)

        # Priority alone decides: the higher-priority (but now not
        # ready) entry still sorts first.
        assert ordered[0].task_id == stale.task_id

    def test_peek_integrates_readiness_by_default(self):
        lifecycle_service, readiness_service, queue_service = _services()
        stale = _ready_task(lifecycle_service)
        fresh = _ready_task(lifecycle_service)
        queue_service.enqueue(stale.task_id, priority=100)
        queue_service.enqueue(fresh.task_id, priority=1)
        lifecycle_service.transition(stale.task_id, RUNNING)

        ordered = queue_service.peek()

        assert ordered[0].task_id == fresh.task_id


class TestDeterminism:
    def test_repeated_order_calls_are_identical(self):
        lifecycle_service, _, queue_service = _services()
        for i in range(5):
            task = _ready_task(lifecycle_service)
            queue_service.enqueue(task.task_id, priority=i)

        ordering_service = LLMAgentTaskQueueOrderingService()
        entries = queue_service.peek()

        first = [e.task_id for e in ordering_service.order(entries)]
        second = [e.task_id for e in ordering_service.order(entries)]
        assert first == second


class TestEmptyAndSingle:
    def test_order_empty_list(self):
        ordering_service = LLMAgentTaskQueueOrderingService()
        assert ordering_service.order([]) == []

    def test_next_empty_list_is_none(self):
        ordering_service = LLMAgentTaskQueueOrderingService()
        assert ordering_service.next([]) is None

    def test_order_single_entry(self):
        lifecycle_service, _, queue_service = _services()
        task = _ready_task(lifecycle_service)
        entry = queue_service.enqueue(task.task_id)

        ordering_service = LLMAgentTaskQueueOrderingService()
        ordered = ordering_service.order([entry])

        assert ordered == [entry]

    def test_next_single_entry(self):
        lifecycle_service, _, queue_service = _services()
        task = _ready_task(lifecycle_service)
        entry = queue_service.enqueue(task.task_id)

        ordering_service = LLMAgentTaskQueueOrderingService()
        assert ordering_service.next([entry]) == entry


class TestNoMutation:
    def test_order_does_not_mutate_input_list_or_entries(self):
        lifecycle_service, _, queue_service = _services()
        low = _ready_task(lifecycle_service)
        high = _ready_task(lifecycle_service)
        low_entry = queue_service.enqueue(low.task_id, priority=1)
        high_entry = queue_service.enqueue(high.task_id, priority=10)

        original_list = [low_entry, high_entry]
        snapshot = list(original_list)

        ordering_service = LLMAgentTaskQueueOrderingService()
        ordering_service.order(original_list)

        assert original_list == snapshot
        assert low_entry.priority == 1
        assert high_entry.priority == 10


class TestInvalidInput:
    def test_order_rejects_non_list(self):
        ordering_service = LLMAgentTaskQueueOrderingService()
        with pytest.raises(InvalidQueueEntryError):
            ordering_service.order("not-a-list")

    def test_order_rejects_non_entry_items(self):
        ordering_service = LLMAgentTaskQueueOrderingService()
        with pytest.raises(InvalidQueueEntryError):
            ordering_service.order([{"task_id": "x"}])

    def test_compare_rejects_non_entry(self):
        lifecycle_service, _, queue_service = _services()
        task = _ready_task(lifecycle_service)
        entry = queue_service.enqueue(task.task_id)

        ordering_service = LLMAgentTaskQueueOrderingService()
        with pytest.raises(InvalidQueueEntryError):
            ordering_service.compare(entry, "not-an-entry")
