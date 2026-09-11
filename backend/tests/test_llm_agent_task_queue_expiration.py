from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_lifecycle import PLANNED, READY, LLMAgentTaskLifecycleService
from backend.agent_task_queue import InvalidQueueEntryError, LLMAgentTaskQueueService
from backend.agent_task_queue_expiration import LLMAgentTaskQueueExpirationService
from backend.agent_task_queue_reservation import LLMAgentTaskQueueReservationService
from backend.agent_task_readiness import LLMAgentTaskReadinessService

MAX_AGE = timedelta(minutes=10)


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _services(max_queue_age=MAX_AGE, reservation_default_ttl=None):
    lifecycle_service = LLMAgentTaskLifecycleService()
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)
    queue_service = LLMAgentTaskQueueService(readiness_service)
    reservation_service = LLMAgentTaskQueueReservationService(queue_service, default_ttl=reservation_default_ttl)
    expiration_service = LLMAgentTaskQueueExpirationService(queue_service, reservation_service, max_queue_age)
    return lifecycle_service, queue_service, reservation_service, expiration_service


def _ready_task(lifecycle_service, **overrides):
    task = lifecycle_service.create(_definition(**overrides))
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    return task


class TestUnexpiredEntry:
    def test_unexpired_entry_remains_queued(self):
        lifecycle_service, queue_service, _, expiration_service = _services()
        task = _ready_task(lifecycle_service)
        entry = queue_service.enqueue(task.task_id)

        soon = entry.queued_at + timedelta(minutes=1)
        result = expiration_service.expire_all(now=soon)

        assert result.expired_tasks == []
        assert result.removed_entries == []
        assert queue_service.contains(task.task_id)

    def test_find_expired_ignores_unexpired(self):
        lifecycle_service, queue_service, _, expiration_service = _services()
        task = _ready_task(lifecycle_service)
        entry = queue_service.enqueue(task.task_id)

        soon = entry.queued_at + timedelta(minutes=1)
        assert expiration_service.find_expired(now=soon) == []


class TestExpiredEntryDetected:
    def test_find_expired_detects_past_lifetime_entry(self):
        lifecycle_service, queue_service, _, expiration_service = _services()
        task = _ready_task(lifecycle_service)
        entry = queue_service.enqueue(task.task_id)

        later = entry.queued_at + MAX_AGE + timedelta(seconds=1)
        found = expiration_service.find_expired(now=later)

        assert [e.task_id for e in found] == [task.task_id]

    def test_expire_removes_expired_unreserved_entry(self):
        lifecycle_service, queue_service, _, expiration_service = _services()
        task = _ready_task(lifecycle_service)
        entry = queue_service.enqueue(task.task_id)

        later = entry.queued_at + MAX_AGE + timedelta(seconds=1)
        result = expiration_service.expire(task.task_id, now=later)

        assert result.expired_tasks == [task.task_id]
        assert [e.task_id for e in result.removed_entries] == [task.task_id]
        assert result.skipped_tasks == []
        assert not queue_service.contains(task.task_id)


class TestExpiredReservationHandled:
    def test_expire_all_releases_stale_reservation_and_removes_entry(self):
        lifecycle_service, queue_service, reservation_service, expiration_service = _services(
            reservation_default_ttl=timedelta(seconds=-1)
        )
        task = _ready_task(lifecycle_service)
        entry = queue_service.enqueue(task.task_id)
        reservation_service.reserve(task.task_id, "worker-1")  # immediately stale

        later = entry.queued_at + MAX_AGE + timedelta(seconds=1)
        result = expiration_service.expire_all(now=later)

        assert [e.task_id for e in result.removed_entries] == [task.task_id]
        assert reservation_service.get_reservation(task.task_id) is None
        assert not queue_service.contains(task.task_id)

    def test_active_reservation_protects_entry_from_removal(self):
        lifecycle_service, queue_service, reservation_service, expiration_service = _services()
        task = _ready_task(lifecycle_service)
        entry = queue_service.enqueue(task.task_id)
        reservation_service.reserve(task.task_id, "worker-1")

        later = entry.queued_at + MAX_AGE + timedelta(seconds=1)
        result = expiration_service.expire_all(now=later)

        assert result.expired_tasks == [task.task_id]
        assert result.skipped_tasks == [task.task_id]
        assert result.removed_entries == []
        assert queue_service.contains(task.task_id)
        assert reservation_service.is_reservation_valid(task.task_id)


class TestMultipleExpiredEntries:
    def test_expire_all_processes_every_expired_entry(self):
        lifecycle_service, queue_service, _, expiration_service = _services()
        tasks = [_ready_task(lifecycle_service) for _ in range(3)]
        entries = [queue_service.enqueue(t.task_id) for t in tasks]

        later = max(e.queued_at for e in entries) + MAX_AGE + timedelta(seconds=1)
        result = expiration_service.expire_all(now=later)

        assert set(result.expired_tasks) == {t.task_id for t in tasks}
        assert {e.task_id for e in result.removed_entries} == {t.task_id for t in tasks}
        for t in tasks:
            assert not queue_service.contains(t.task_id)


class TestMixedValidExpiredQueue:
    def test_expire_all_only_removes_the_expired_ones(self):
        lifecycle_service, queue_service, _, expiration_service = _services()
        old_task = _ready_task(lifecycle_service)
        old_entry = queue_service.enqueue(old_task.task_id)

        later = old_entry.queued_at + MAX_AGE + timedelta(seconds=1)

        # Backdate-free control over queued_at: enqueue normally, then
        # overwrite the stored entry's own queued_at to sit just before
        # `later`, so this entry is deliberately still within its own
        # lifetime at `later` regardless of real wall-clock spacing
        # between the two enqueue() calls in this test.
        fresh_task = _ready_task(lifecycle_service)
        fresh_entry = queue_service.enqueue(fresh_task.task_id)
        fresh_entry = replace(fresh_entry, queued_at=later - timedelta(seconds=1))
        queue_service.store.save(fresh_entry)

        result = expiration_service.expire_all(now=later)

        assert result.expired_tasks == [old_task.task_id]
        assert not queue_service.contains(old_task.task_id)
        assert queue_service.contains(fresh_task.task_id)


class TestMissingEntry:
    def test_expire_missing_task_is_safe(self):
        _, _, _, expiration_service = _services()

        result = expiration_service.expire("no-such-task", now=datetime.now(timezone.utc))

        assert result.expired_tasks == []
        assert result.removed_entries == []
        assert result.skipped_tasks == []
        assert len(result.errors) == 1
        assert result.errors[0][0] == "no-such-task"

    def test_expire_requires_task_id(self):
        _, _, _, expiration_service = _services()
        with pytest.raises(InvalidQueueEntryError):
            expiration_service.expire("")

    def test_expire_rejects_non_datetime_now(self):
        _, _, _, expiration_service = _services()
        with pytest.raises(InvalidQueueEntryError):
            expiration_service.expire("some-task", now="not-a-datetime")


class TestRepeatedExpirationIdempotent:
    def test_repeated_expire_all_produces_no_duplicate_changes(self):
        lifecycle_service, queue_service, _, expiration_service = _services()
        task = _ready_task(lifecycle_service)
        entry = queue_service.enqueue(task.task_id)

        later = entry.queued_at + MAX_AGE + timedelta(seconds=1)
        first = expiration_service.expire_all(now=later)
        second = expiration_service.expire_all(now=later)

        assert first.removed_entries != []
        assert second.expired_tasks == []
        assert second.removed_entries == []
        assert second.skipped_tasks == []

    def test_repeated_expire_single_task_is_safe(self):
        lifecycle_service, queue_service, _, expiration_service = _services()
        task = _ready_task(lifecycle_service)
        entry = queue_service.enqueue(task.task_id)

        later = entry.queued_at + MAX_AGE + timedelta(seconds=1)
        first = expiration_service.expire(task.task_id, now=later)
        second = expiration_service.expire(task.task_id, now=later)

        assert first.removed_entries != []
        assert second.expired_tasks == []
        assert len(second.errors) == 1  # now not queued at all -- safe, not a duplicate removal
