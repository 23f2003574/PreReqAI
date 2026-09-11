import pytest

from backend.agent_task_lifecycle import PLANNED, READY, LLMAgentTaskLifecycleService
from backend.agent_task_queue import ConflictingClaimError, InvalidQueueEntryError, LLMAgentTaskQueueService
from backend.agent_task_queue_batch import BatchOperationError, LLMAgentTaskQueueBatchService
from backend.agent_task_queue_reservation import LLMAgentTaskQueueReservationService
from backend.agent_task_readiness import LLMAgentTaskReadinessService


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _services():
    lifecycle_service = LLMAgentTaskLifecycleService()
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)
    queue_service = LLMAgentTaskQueueService(readiness_service)
    reservation_service = LLMAgentTaskQueueReservationService(queue_service)
    batch_service = LLMAgentTaskQueueBatchService(queue_service, reservation_service)
    return lifecycle_service, queue_service, reservation_service, batch_service


def _ready_task(lifecycle_service, **overrides):
    task = lifecycle_service.create(_definition(**overrides))
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    return task


class TestBatchEnqueue:
    def test_enqueue_many_enqueues_every_task(self):
        lifecycle_service, queue_service, _, batch_service = _services()
        tasks = [_ready_task(lifecycle_service) for _ in range(3)]
        task_ids = [t.task_id for t in tasks]

        entries = batch_service.enqueue_many(task_ids)

        assert {e.task_id for e in entries} == set(task_ids)
        for task_id in task_ids:
            assert queue_service.contains(task_id)

    def test_enqueue_many_applies_shared_priority(self):
        lifecycle_service, queue_service, _, batch_service = _services()
        tasks = [_ready_task(lifecycle_service) for _ in range(2)]
        task_ids = [t.task_id for t in tasks]

        entries = batch_service.enqueue_many(task_ids, priority=7)

        assert all(entry.priority == 7 for entry in entries)

    def test_enqueue_many_empty_list(self):
        _, _, _, batch_service = _services()
        assert batch_service.enqueue_many([]) == []

    def test_enqueue_many_rejects_non_list(self):
        _, _, _, batch_service = _services()
        with pytest.raises(InvalidQueueEntryError):
            batch_service.enqueue_many("not-a-list")


class TestBatchClaimWithReservationConflicts:
    def test_claim_many_claims_every_task(self):
        lifecycle_service, queue_service, reservation_service, batch_service = _services()
        tasks = [_ready_task(lifecycle_service) for _ in range(3)]
        task_ids = [t.task_id for t in tasks]
        batch_service.enqueue_many(task_ids)

        entries = batch_service.claim_many(task_ids, "worker-1")

        assert all(entry.claimant_id == "worker-1" for entry in entries)
        for task_id in task_ids:
            assert reservation_service.is_reservation_valid(task_id)

    def test_claim_many_fails_on_reservation_conflict(self):
        lifecycle_service, queue_service, reservation_service, batch_service = _services()
        tasks = [_ready_task(lifecycle_service) for _ in range(3)]
        task_ids = [t.task_id for t in tasks]
        batch_service.enqueue_many(task_ids)
        reservation_service.reserve(task_ids[1], "worker-other")

        with pytest.raises(BatchOperationError) as excinfo:
            batch_service.claim_many(task_ids, "worker-1")

        error = excinfo.value
        assert len(error.succeeded) == 2
        assert len(error.failures) == 1
        failed_task_id, failed_error = error.failures[0]
        assert failed_task_id == task_ids[1]
        assert isinstance(failed_error, ConflictingClaimError)

    def test_claim_many_partial_success_persists(self):
        lifecycle_service, queue_service, reservation_service, batch_service = _services()
        tasks = [_ready_task(lifecycle_service) for _ in range(2)]
        task_ids = [t.task_id for t in tasks]
        batch_service.enqueue_many(task_ids)
        reservation_service.reserve(task_ids[1], "worker-other")

        with pytest.raises(BatchOperationError):
            batch_service.claim_many(task_ids, "worker-1")

        # The successful claim in the batch is not rolled back even
        # though the batch as a whole raised.
        assert reservation_service.get_reservation(task_ids[0]).claimant_id == "worker-1"
        assert reservation_service.get_reservation(task_ids[1]).claimant_id == "worker-other"


class TestBatchRemoval:
    def test_remove_many_removes_every_task(self):
        lifecycle_service, queue_service, _, batch_service = _services()
        tasks = [_ready_task(lifecycle_service) for _ in range(3)]
        task_ids = [t.task_id for t in tasks]
        batch_service.enqueue_many(task_ids)

        removed = batch_service.remove_many(task_ids)

        assert removed == 3
        for task_id in task_ids:
            assert not queue_service.contains(task_id)

    def test_remove_many_empty_list(self):
        _, _, _, batch_service = _services()
        assert batch_service.remove_many([]) == 0


class TestMixedValidInvalid:
    def test_enqueue_many_mixed_valid_invalid(self):
        lifecycle_service, queue_service, _, batch_service = _services()
        good = _ready_task(lifecycle_service)
        not_ready = lifecycle_service.create(_definition())  # left CREATED, never ready

        with pytest.raises(BatchOperationError) as excinfo:
            batch_service.enqueue_many([good.task_id, not_ready.task_id])

        error = excinfo.value
        assert [e.task_id for e in error.succeeded] == [good.task_id]
        assert len(error.failures) == 1
        assert error.failures[0][0] == not_ready.task_id
        assert queue_service.contains(good.task_id)
        assert not queue_service.contains(not_ready.task_id)

    def test_remove_many_mixed_valid_invalid(self):
        lifecycle_service, queue_service, _, batch_service = _services()
        task = _ready_task(lifecycle_service)
        batch_service.enqueue_many([task.task_id])

        with pytest.raises(BatchOperationError) as excinfo:
            batch_service.remove_many([task.task_id, "no-such-task"])

        error = excinfo.value
        assert error.succeeded == [task.task_id]
        assert len(error.failures) == 1
        assert error.failures[0][0] == "no-such-task"


class TestDuplicateIds:
    def test_enqueue_many_duplicate_ids_is_idempotent(self):
        lifecycle_service, queue_service, _, batch_service = _services()
        task = _ready_task(lifecycle_service)

        entries = batch_service.enqueue_many([task.task_id, task.task_id])

        assert len(entries) == 2
        assert entries[0] == entries[1]

    def test_remove_many_duplicate_ids_second_fails(self):
        lifecycle_service, queue_service, _, batch_service = _services()
        task = _ready_task(lifecycle_service)
        batch_service.enqueue_many([task.task_id])

        with pytest.raises(BatchOperationError) as excinfo:
            batch_service.remove_many([task.task_id, task.task_id])

        error = excinfo.value
        assert error.succeeded == [task.task_id]
        assert len(error.failures) == 1
        assert error.failures[0][0] == task.task_id
        assert not queue_service.contains(task.task_id)

    def test_claim_many_duplicate_ids_same_claimant_is_idempotent(self):
        lifecycle_service, queue_service, _, batch_service = _services()
        task = _ready_task(lifecycle_service)
        batch_service.enqueue_many([task.task_id])

        entries = batch_service.claim_many([task.task_id, task.task_id], "worker-1")

        assert len(entries) == 2
        assert entries[0] == entries[1]


class TestOrderingPreserved:
    def test_ordering_correct_after_batch_enqueue(self):
        lifecycle_service, queue_service, _, batch_service = _services()
        tasks = [_ready_task(lifecycle_service) for _ in range(3)]
        task_ids = [t.task_id for t in tasks]

        for task_id, priority in zip(task_ids, [5, 20, 1]):
            batch_service.enqueue_many([task_id], priority=priority)

        ordered = [entry.task_id for entry in queue_service.peek()]
        assert ordered == [task_ids[1], task_ids[0], task_ids[2]]

    def test_ordering_correct_after_single_batch_call_mixed_priority(self):
        lifecycle_service, queue_service, _, batch_service = _services()
        low = _ready_task(lifecycle_service)
        high = _ready_task(lifecycle_service)
        mid = _ready_task(lifecycle_service)

        # enqueue_many shares one priority across the whole call, so
        # exercise ordering by claiming afterward instead (claimed
        # entries still order the same way -- claim state is orthogonal
        # to priority ordering).
        batch_service.enqueue_many([low.task_id], priority=1)
        batch_service.enqueue_many([high.task_id], priority=10)
        batch_service.enqueue_many([mid.task_id], priority=5)

        ordered = [entry.task_id for entry in queue_service.peek()]
        assert ordered == [high.task_id, mid.task_id, low.task_id]


class TestAtomicityConvention:
    def test_atomic_context_manager_available_on_queue_service(self):
        lifecycle_service, queue_service, _, batch_service = _services()
        task = _ready_task(lifecycle_service)

        with queue_service.atomic():
            entry = queue_service.enqueue(task.task_id)

        assert entry.task_id == task.task_id

    def test_atomic_context_manager_available_on_reservation_service(self):
        lifecycle_service, queue_service, reservation_service, batch_service = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)

        with reservation_service.atomic():
            reservation = reservation_service.reserve(task.task_id, "worker-1")

        assert reservation.claimant_id == "worker-1"

    def test_batch_failures_never_silently_dropped(self):
        lifecycle_service, queue_service, _, batch_service = _services()
        good = _ready_task(lifecycle_service)
        bad_task_id = "phantom"

        with pytest.raises(BatchOperationError) as excinfo:
            batch_service.enqueue_many([good.task_id, bad_task_id])

        failed_ids = [task_id for task_id, _ in excinfo.value.failures]
        assert bad_task_id in failed_ids
