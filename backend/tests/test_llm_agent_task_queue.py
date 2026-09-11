import pytest

from backend.agent_task_lifecycle import PLANNED, READY, LLMAgentTaskLifecycleService
from backend.agent_task_queue import (
    ConflictingClaimError,
    InMemoryAgentTaskQueueStore,
    InvalidQueueEntryError,
    LLMAgentTaskQueueService,
    QueueEntry,
    TaskNotReadyError,
    UnknownQueueEntryError,
)
from backend.agent_task_readiness import LLMAgentTaskReadinessService


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _services():
    lifecycle_service = LLMAgentTaskLifecycleService()
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)
    queue_service = LLMAgentTaskQueueService(readiness_service)
    return lifecycle_service, queue_service


def _ready_task(lifecycle_service, **overrides):
    task = lifecycle_service.create(_definition(**overrides))
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    return task


class TestEnqueuePeekRemove:
    def test_enqueue_returns_queue_entry(self):
        lifecycle_service, queue_service = _services()
        task = _ready_task(lifecycle_service)

        entry = queue_service.enqueue(task.task_id)

        assert isinstance(entry, QueueEntry)
        assert entry.task_id == task.task_id
        assert entry.priority == 0
        assert entry.claimant_id is None
        assert entry.claimed_at is None
        assert entry.queued_at is not None

    def test_peek_lists_enqueued_entries(self):
        lifecycle_service, queue_service = _services()
        task_a = _ready_task(lifecycle_service)
        task_b = _ready_task(lifecycle_service)

        queue_service.enqueue(task_a.task_id)
        queue_service.enqueue(task_b.task_id)

        entries = queue_service.peek()
        assert {entry.task_id for entry in entries} == {task_a.task_id, task_b.task_id}

    def test_peek_respects_limit(self):
        lifecycle_service, queue_service = _services()
        for _ in range(3):
            task = _ready_task(lifecycle_service)
            queue_service.enqueue(task.task_id)

        assert len(queue_service.peek(limit=2)) == 2
        assert len(queue_service.peek(limit=0)) == 0
        assert len(queue_service.peek()) == 3

    def test_peek_invalid_limit_raises(self):
        _, queue_service = _services()
        with pytest.raises(InvalidQueueEntryError):
            queue_service.peek(limit=-1)
        with pytest.raises(InvalidQueueEntryError):
            queue_service.peek(limit="two")

    def test_remove_deletes_entry(self):
        lifecycle_service, queue_service = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)

        queue_service.remove(task.task_id)

        assert queue_service.contains(task.task_id) is False
        assert queue_service.peek() == []

    def test_remove_does_not_change_lifecycle_state(self):
        lifecycle_service, queue_service = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)

        queue_service.remove(task.task_id)

        assert lifecycle_service.get(task.task_id).current_state == READY

    def test_enqueue_invalid_task_id_raises(self):
        _, queue_service = _services()
        with pytest.raises(InvalidQueueEntryError):
            queue_service.enqueue("")
        with pytest.raises(InvalidQueueEntryError):
            queue_service.enqueue(None)


class TestPriorityOrdering:
    def test_peek_orders_by_priority_descending(self):
        lifecycle_service, queue_service = _services()
        low = _ready_task(lifecycle_service)
        high = _ready_task(lifecycle_service)
        mid = _ready_task(lifecycle_service)

        queue_service.enqueue(low.task_id, priority=1)
        queue_service.enqueue(high.task_id, priority=10)
        queue_service.enqueue(mid.task_id, priority=5)

        ordered = [entry.task_id for entry in queue_service.peek()]
        assert ordered == [high.task_id, mid.task_id, low.task_id]

    def test_peek_orders_equal_priority_fifo(self):
        lifecycle_service, queue_service = _services()
        first = _ready_task(lifecycle_service)
        second = _ready_task(lifecycle_service)

        entry_first = queue_service.enqueue(first.task_id, priority=3)
        entry_second = queue_service.enqueue(second.task_id, priority=3)

        ordered = [entry.task_id for entry in queue_service.peek()]
        # Deterministic tie-break: queued_at, then task_id -- whichever
        # was actually enqueued first (or has the lexically smaller
        # task_id on an exact timestamp tie) sorts first.
        expected_first = (
            first.task_id
            if entry_first.queued_at != entry_second.queued_at
            else min(first.task_id, second.task_id)
        )
        assert ordered[0] == expected_first

    def test_enqueue_without_priority_defaults_to_zero(self):
        lifecycle_service, queue_service = _services()
        task = _ready_task(lifecycle_service)

        entry = queue_service.enqueue(task.task_id)

        assert entry.priority == 0

    def test_enqueue_invalid_priority_raises(self):
        lifecycle_service, queue_service = _services()
        task = _ready_task(lifecycle_service)
        with pytest.raises(InvalidQueueEntryError):
            queue_service.enqueue(task.task_id, priority="high")


class TestDuplicateEnqueue:
    def test_repeated_enqueue_is_idempotent(self):
        lifecycle_service, queue_service = _services()
        task = _ready_task(lifecycle_service)

        first = queue_service.enqueue(task.task_id, priority=1)
        second = queue_service.enqueue(task.task_id, priority=9)

        assert second == first
        assert second.priority == 1
        assert len(queue_service.peek()) == 1

    def test_repeated_enqueue_after_claim_returns_claimed_entry(self):
        lifecycle_service, queue_service = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)
        claimed = queue_service.claim(task.task_id, "worker-1")

        again = queue_service.enqueue(task.task_id)

        assert again == claimed
        assert again.claimant_id == "worker-1"


class TestReadinessGating:
    def test_enqueue_ready_task_succeeds(self):
        lifecycle_service, queue_service = _services()
        task = _ready_task(lifecycle_service)

        entry = queue_service.enqueue(task.task_id)

        assert entry.task_id == task.task_id

    def test_enqueue_non_ready_task_raises(self):
        lifecycle_service, queue_service = _services()
        task = lifecycle_service.create(_definition())  # left in CREATED state

        with pytest.raises(TaskNotReadyError):
            queue_service.enqueue(task.task_id)

        assert queue_service.contains(task.task_id) is False

    def test_enqueue_unknown_task_raises_not_ready(self):
        _, queue_service = _services()

        with pytest.raises(TaskNotReadyError):
            queue_service.enqueue("no-such-task")


class TestClaimExclusivity:
    def test_claim_assigns_claimant(self):
        lifecycle_service, queue_service = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)

        claimed = queue_service.claim(task.task_id, "worker-1")

        assert claimed.claimant_id == "worker-1"
        assert claimed.claimed_at is not None

    def test_reclaim_by_same_claimant_is_noop(self):
        lifecycle_service, queue_service = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)
        first = queue_service.claim(task.task_id, "worker-1")

        second = queue_service.claim(task.task_id, "worker-1")

        assert second == first

    def test_claim_by_different_claimant_conflicts(self):
        lifecycle_service, queue_service = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)
        queue_service.claim(task.task_id, "worker-1")

        with pytest.raises(ConflictingClaimError):
            queue_service.claim(task.task_id, "worker-2")

    def test_claim_requires_claimant_id(self):
        lifecycle_service, queue_service = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)

        with pytest.raises(InvalidQueueEntryError):
            queue_service.claim(task.task_id, "")


class TestMissingTaskOrEntry:
    def test_claim_missing_entry_raises(self):
        _, queue_service = _services()
        with pytest.raises(UnknownQueueEntryError):
            queue_service.claim("no-such-task", "worker-1")

    def test_remove_missing_entry_raises(self):
        _, queue_service = _services()
        with pytest.raises(UnknownQueueEntryError):
            queue_service.remove("no-such-task")

    def test_contains_missing_entry_is_false(self):
        _, queue_service = _services()
        assert queue_service.contains("no-such-task") is False


class TestIsolation:
    def test_separate_service_instances_do_not_share_entries(self):
        lifecycle_service, first_queue = _services()
        readiness_service = LLMAgentTaskReadinessService(lifecycle_service)
        second_queue = LLMAgentTaskQueueService(readiness_service, store=InMemoryAgentTaskQueueStore())

        task = _ready_task(lifecycle_service)
        first_queue.enqueue(task.task_id)

        assert first_queue.contains(task.task_id) is True
        assert second_queue.contains(task.task_id) is False
        assert second_queue.peek() == []

    def test_distinct_tasks_do_not_interfere(self):
        lifecycle_service, queue_service = _services()
        task_a = _ready_task(lifecycle_service)
        task_b = _ready_task(lifecycle_service)

        queue_service.enqueue(task_a.task_id)
        queue_service.enqueue(task_b.task_id)
        queue_service.claim(task_a.task_id, "worker-1")

        assert queue_service.claim(task_b.task_id, "worker-2").claimant_id == "worker-2"

        queue_service.remove(task_a.task_id)

        assert queue_service.contains(task_a.task_id) is False
        assert queue_service.contains(task_b.task_id) is True
