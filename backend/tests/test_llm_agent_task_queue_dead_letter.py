import pytest

from backend.agent_task_lifecycle import PLANNED, READY, RUNNING, LLMAgentTaskLifecycleService
from backend.agent_task_queue import InvalidQueueEntryError, LLMAgentTaskQueueService, TaskNotReadyError
from backend.agent_task_queue_dead_letter import DeadLetterEntry, LLMAgentTaskDeadLetterService
from backend.agent_task_queue_selection import LLMAgentTaskQueueSelectionService
from backend.agent_task_queue_reservation import LLMAgentTaskQueueReservationService
from backend.agent_task_readiness import LLMAgentTaskReadinessService
from backend.agent_task_state_history import LLMAgentTaskStateHistoryService
from backend.agent_task_state_history.tracked import LLMAgentTaskLifecycleHistoryTrackedService


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _services(with_history=False):
    if with_history:
        history_service = LLMAgentTaskStateHistoryService()
        lifecycle_service = LLMAgentTaskLifecycleHistoryTrackedService(history_service=history_service)
    else:
        history_service = None
        lifecycle_service = LLMAgentTaskLifecycleService()

    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)
    queue_service = LLMAgentTaskQueueService(readiness_service)
    reservation_service = LLMAgentTaskQueueReservationService(queue_service)
    selection_service = LLMAgentTaskQueueSelectionService(queue_service, readiness_service, reservation_service)
    dead_letter_service = LLMAgentTaskDeadLetterService(
        queue_service, lifecycle_service, state_history_service=history_service
    )
    return lifecycle_service, queue_service, selection_service, dead_letter_service, history_service


def _ready_task(lifecycle_service, **overrides):
    task = lifecycle_service.create(_definition(**overrides))
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    return task


class TestExcludedFromSelection:
    def test_dead_lettered_task_excluded_from_selection(self):
        lifecycle_service, queue_service, selection_service, dead_letter_service, _ = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id, priority=100)

        dead_letter_service.dead_letter(task.task_id, "exceeded max retries")

        assert selection_service.select(task.task_id) is None
        assert task.task_id not in [e.task_id for e in selection_service.select_next(limit=10)]
        assert queue_service.contains(task.task_id) is False


class TestFailureReasonPreserved:
    def test_reason_preserved_on_entry(self):
        lifecycle_service, queue_service, _, dead_letter_service, _ = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)

        entry = dead_letter_service.dead_letter(task.task_id, "exceeded max retries")

        assert isinstance(entry, DeadLetterEntry)
        assert entry.task_id == task.task_id
        assert entry.reason == "exceeded max retries"
        assert entry.failed_at is not None

    def test_metadata_captures_existing_lifecycle_state(self):
        lifecycle_service, queue_service, _, dead_letter_service, _ = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)
        lifecycle_service.transition(task.task_id, RUNNING, reason="worker picked it up")

        entry = dead_letter_service.dead_letter(task.task_id, "crashed during execution")

        assert entry.metadata["lifecycle_state"] == RUNNING
        assert entry.metadata["previous_state"] == READY
        assert entry.metadata["transition_reason"] == "worker picked it up"

    def test_metadata_includes_latest_transition_when_history_available(self):
        lifecycle_service, queue_service, _, dead_letter_service, history_service = _services(with_history=True)
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)
        lifecycle_service.transition(task.task_id, RUNNING, reason="worker picked it up")

        entry = dead_letter_service.dead_letter(task.task_id, "crashed during execution")

        assert "latest_transition" in entry.metadata
        assert entry.metadata["latest_transition"]["to_state"] == RUNNING
        assert entry.metadata["latest_transition"]["reason"] == "worker picked it up"


class TestTaskItselfIntact:
    def test_task_lifecycle_record_untouched(self):
        lifecycle_service, queue_service, _, dead_letter_service, _ = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)

        dead_letter_service.dead_letter(task.task_id, "manually excluded")

        current = lifecycle_service.get(task.task_id)
        assert current.current_state == READY
        assert current.task_id == task.task_id


class TestRestoreEligibleTask:
    def test_restore_returns_ready_task_to_queue(self):
        lifecycle_service, queue_service, _, dead_letter_service, _ = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id, priority=9)

        dead_letter_service.dead_letter(task.task_id, "manually excluded")
        assert queue_service.contains(task.task_id) is False

        dead_letter_service.restore(task.task_id)

        assert queue_service.contains(task.task_id) is True
        assert dead_letter_service.get(task.task_id) is None


class TestRestoreNonReadyBlocked:
    def test_restore_of_non_ready_task_raises_and_keeps_entry(self):
        lifecycle_service, queue_service, _, dead_letter_service, _ = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)
        dead_letter_service.dead_letter(task.task_id, "crashed")

        # Task can never become ready again once past READY (no path
        # back to READY in Commit #1's own TRANSITIONS graph), so
        # restore() must be rejected via the same readiness gate
        # enqueue() itself already enforces.
        lifecycle_service.transition(task.task_id, RUNNING)

        with pytest.raises(TaskNotReadyError):
            dead_letter_service.restore(task.task_id)

        assert dead_letter_service.get(task.task_id) is not None
        assert queue_service.contains(task.task_id) is False


class TestDuplicateOperationsSafe:
    def test_repeated_dead_letter_returns_existing_entry(self):
        lifecycle_service, queue_service, _, dead_letter_service, _ = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)

        first = dead_letter_service.dead_letter(task.task_id, "reason one")
        second = dead_letter_service.dead_letter(task.task_id, "reason two")

        assert second == first
        assert second.reason == "reason one"

    def test_repeated_restore_is_safe_noop(self):
        lifecycle_service, queue_service, _, dead_letter_service, _ = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)
        dead_letter_service.dead_letter(task.task_id, "manually excluded")

        dead_letter_service.restore(task.task_id)
        dead_letter_service.restore(task.task_id)  # must not raise

        assert queue_service.contains(task.task_id) is True

    def test_restore_of_never_dead_lettered_task_is_safe_noop(self):
        lifecycle_service, queue_service, _, dead_letter_service, _ = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)

        dead_letter_service.restore(task.task_id)  # must not raise

        assert queue_service.contains(task.task_id) is True


class TestMultipleDeadLetteredTasksIsolated:
    def test_multiple_entries_remain_isolated(self):
        lifecycle_service, queue_service, _, dead_letter_service, _ = _services()
        a = _ready_task(lifecycle_service)
        b = _ready_task(lifecycle_service)
        queue_service.enqueue(a.task_id)
        queue_service.enqueue(b.task_id)

        dead_letter_service.dead_letter(a.task_id, "reason a")
        dead_letter_service.dead_letter(b.task_id, "reason b")

        assert dead_letter_service.get(a.task_id).reason == "reason a"
        assert dead_letter_service.get(b.task_id).reason == "reason b"

        dead_letter_service.restore(a.task_id)

        assert dead_letter_service.get(a.task_id) is None
        assert dead_letter_service.get(b.task_id) is not None
        assert queue_service.contains(a.task_id) is True
        assert queue_service.contains(b.task_id) is False

    def test_list_returns_every_entry_oldest_first(self):
        lifecycle_service, queue_service, _, dead_letter_service, _ = _services()
        tasks = [_ready_task(lifecycle_service) for _ in range(3)]
        for t in tasks:
            queue_service.enqueue(t.task_id)
        for t in tasks:
            dead_letter_service.dead_letter(t.task_id, f"reason for {t.task_id}")

        listed = dead_letter_service.list()

        assert [e.task_id for e in listed] == [t.task_id for t in tasks]

    def test_list_respects_limit(self):
        lifecycle_service, queue_service, _, dead_letter_service, _ = _services()
        tasks = [_ready_task(lifecycle_service) for _ in range(3)]
        for t in tasks:
            queue_service.enqueue(t.task_id)
            dead_letter_service.dead_letter(t.task_id, "reason")

        assert len(dead_letter_service.list(limit=2)) == 2


class TestInvalidInput:
    def test_dead_letter_requires_task_id_and_reason(self):
        _, _, _, dead_letter_service, _ = _services()
        with pytest.raises(InvalidQueueEntryError):
            dead_letter_service.dead_letter("", "reason")

    def test_dead_letter_requires_reason(self):
        lifecycle_service, queue_service, _, dead_letter_service, _ = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)
        with pytest.raises(InvalidQueueEntryError):
            dead_letter_service.dead_letter(task.task_id, "")

    def test_restore_requires_task_id(self):
        _, _, _, dead_letter_service, _ = _services()
        with pytest.raises(InvalidQueueEntryError):
            dead_letter_service.restore("")
