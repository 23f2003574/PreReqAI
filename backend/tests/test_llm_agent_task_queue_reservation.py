from datetime import timedelta

import pytest

from backend.agent_task_lifecycle import PLANNED, READY, LLMAgentTaskLifecycleService
from backend.agent_task_queue import ConflictingClaimError, LLMAgentTaskQueueService, UnknownQueueEntryError
from backend.agent_task_queue_reservation import (
    InvalidReservationError,
    LLMAgentTaskQueueReservationService,
    QueueReservation,
)
from backend.agent_task_readiness import LLMAgentTaskReadinessService


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _services(default_ttl=None):
    lifecycle_service = LLMAgentTaskLifecycleService()
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)
    queue_service = LLMAgentTaskQueueService(readiness_service)
    reservation_service = LLMAgentTaskQueueReservationService(queue_service, default_ttl=default_ttl)
    return lifecycle_service, queue_service, reservation_service


def _queued_task(lifecycle_service, queue_service, **overrides):
    task = lifecycle_service.create(_definition(**overrides))
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    queue_service.enqueue(task.task_id)
    return task


class TestSuccessfulReservation:
    def test_reserve_returns_reservation(self):
        lifecycle_service, queue_service, reservation_service = _services()
        task = _queued_task(lifecycle_service, queue_service)

        reservation = reservation_service.reserve(task.task_id, "worker-1")

        assert isinstance(reservation, QueueReservation)
        assert reservation.task_id == task.task_id
        assert reservation.claimant_id == "worker-1"
        assert reservation.expires_at > reservation.reserved_at

    def test_reserve_actually_claims_the_underlying_queue_entry(self):
        lifecycle_service, queue_service, reservation_service = _services()
        task = _queued_task(lifecycle_service, queue_service)

        reservation_service.reserve(task.task_id, "worker-1")

        entry = queue_service.peek()[0]
        assert entry.claimant_id == "worker-1"

    def test_reserve_with_explicit_ttl(self):
        lifecycle_service, queue_service, reservation_service = _services()
        task = _queued_task(lifecycle_service, queue_service)

        reservation = reservation_service.reserve(task.task_id, "worker-1", ttl=60)

        assert (reservation.expires_at - reservation.reserved_at) <= timedelta(seconds=61)
        assert (reservation.expires_at - reservation.reserved_at) >= timedelta(seconds=59)

    def test_repeated_reserve_by_same_owner_is_idempotent(self):
        lifecycle_service, queue_service, reservation_service = _services()
        task = _queued_task(lifecycle_service, queue_service)

        first = reservation_service.reserve(task.task_id, "worker-1")
        second = reservation_service.reserve(task.task_id, "worker-1")

        assert second == first

    def test_reserve_invalid_arguments_raise(self):
        lifecycle_service, queue_service, reservation_service = _services()
        task = _queued_task(lifecycle_service, queue_service)

        with pytest.raises(InvalidReservationError):
            reservation_service.reserve("", "worker-1")
        with pytest.raises(InvalidReservationError):
            reservation_service.reserve(task.task_id, "")
        with pytest.raises(InvalidReservationError):
            reservation_service.reserve(task.task_id, "worker-1", ttl=-5)
        with pytest.raises(InvalidReservationError):
            reservation_service.reserve(task.task_id, "worker-1", ttl=0)


class TestConflictingReservation:
    def test_second_claimant_rejected_while_active(self):
        lifecycle_service, queue_service, reservation_service = _services()
        task = _queued_task(lifecycle_service, queue_service)
        reservation_service.reserve(task.task_id, "worker-1")

        with pytest.raises(ConflictingClaimError):
            reservation_service.reserve(task.task_id, "worker-2")

    def test_reservation_unchanged_after_rejected_attempt(self):
        lifecycle_service, queue_service, reservation_service = _services()
        task = _queued_task(lifecycle_service, queue_service)
        original = reservation_service.reserve(task.task_id, "worker-1")

        with pytest.raises(ConflictingClaimError):
            reservation_service.reserve(task.task_id, "worker-2")

        assert reservation_service.get_reservation(task.task_id) == original


class TestRelease:
    def test_owner_can_release(self):
        lifecycle_service, queue_service, reservation_service = _services()
        task = _queued_task(lifecycle_service, queue_service)
        reservation_service.reserve(task.task_id, "worker-1")

        reservation_service.release(task.task_id, "worker-1")

        assert reservation_service.get_reservation(task.task_id) is None
        assert reservation_service.is_reservation_valid(task.task_id) is False

    def test_release_frees_underlying_claim_for_others(self):
        lifecycle_service, queue_service, reservation_service = _services()
        task = _queued_task(lifecycle_service, queue_service)
        reservation_service.reserve(task.task_id, "worker-1")

        reservation_service.release(task.task_id, "worker-1")
        other = reservation_service.reserve(task.task_id, "worker-2")

        assert other.claimant_id == "worker-2"

    def test_non_owner_cannot_release(self):
        lifecycle_service, queue_service, reservation_service = _services()
        task = _queued_task(lifecycle_service, queue_service)
        reservation_service.reserve(task.task_id, "worker-1")

        with pytest.raises(ConflictingClaimError):
            reservation_service.release(task.task_id, "worker-2")

        assert reservation_service.is_reservation_valid(task.task_id) is True

    def test_release_requires_claimant_id(self):
        lifecycle_service, queue_service, reservation_service = _services()
        task = _queued_task(lifecycle_service, queue_service)
        reservation_service.reserve(task.task_id, "worker-1")

        with pytest.raises(InvalidReservationError):
            reservation_service.release(task.task_id, "")


class TestExpiration:
    def test_expired_reservation_reads_as_absent(self):
        lifecycle_service, queue_service, reservation_service = _services(default_ttl=timedelta(seconds=-1))
        task = _queued_task(lifecycle_service, queue_service)

        # reserve() itself calls the queue's claim() before the
        # already-past expires_at is computed, so the underlying claim
        # succeeds even though the resulting reservation is
        # immediately stale.
        reservation_service.reserve(task.task_id, "worker-1")

        assert reservation_service.get_reservation(task.task_id) is None
        assert reservation_service.is_reservation_valid(task.task_id) is False

    def test_expired_reservation_becomes_claimable_by_another(self):
        lifecycle_service, queue_service, reservation_service = _services(default_ttl=timedelta(seconds=-1))
        task = _queued_task(lifecycle_service, queue_service)
        reservation_service.reserve(task.task_id, "worker-1")

        reservation = reservation_service.reserve(task.task_id, "worker-2")

        assert reservation.claimant_id == "worker-2"

    def test_expire_stale_reservations_releases_underlying_claim(self):
        lifecycle_service, queue_service, reservation_service = _services(default_ttl=timedelta(seconds=-1))
        task = _queued_task(lifecycle_service, queue_service)
        reservation_service.reserve(task.task_id, "worker-1")

        cleared = reservation_service.expire_stale_reservations()

        assert cleared == 1
        entry = queue_service.peek()[0]
        assert entry.claimant_id is None

    def test_expire_stale_reservations_ignores_still_valid_ones(self):
        lifecycle_service, queue_service, reservation_service = _services()
        task = _queued_task(lifecycle_service, queue_service)
        reservation_service.reserve(task.task_id, "worker-1")

        cleared = reservation_service.expire_stale_reservations()

        assert cleared == 0
        assert reservation_service.is_reservation_valid(task.task_id) is True


class TestMissingTaskOrEntry:
    def test_reserve_unqueued_task_raises_unknown_queue_entry(self):
        _, _, reservation_service = _services()
        with pytest.raises(UnknownQueueEntryError):
            reservation_service.reserve("no-such-task", "worker-1")

    def test_get_reservation_for_unknown_task_is_none(self):
        _, _, reservation_service = _services()
        assert reservation_service.get_reservation("no-such-task") is None

    def test_is_reservation_valid_for_unknown_task_is_false(self):
        _, _, reservation_service = _services()
        assert reservation_service.is_reservation_valid("no-such-task") is False

    def test_release_for_unknown_task_is_noop(self):
        _, _, reservation_service = _services()
        reservation_service.release("no-such-task", "worker-1")  # must not raise


class TestRepeatedReleaseAndExpiration:
    def test_repeated_release_is_safe(self):
        lifecycle_service, queue_service, reservation_service = _services()
        task = _queued_task(lifecycle_service, queue_service)
        reservation_service.reserve(task.task_id, "worker-1")

        reservation_service.release(task.task_id, "worker-1")
        reservation_service.release(task.task_id, "worker-1")  # must not raise

        assert reservation_service.get_reservation(task.task_id) is None

    def test_repeated_expiration_is_safe_and_deterministic(self):
        lifecycle_service, queue_service, reservation_service = _services(default_ttl=timedelta(seconds=-1))
        task = _queued_task(lifecycle_service, queue_service)
        reservation_service.reserve(task.task_id, "worker-1")

        first = reservation_service.expire_stale_reservations()
        second = reservation_service.expire_stale_reservations()

        assert first == 1
        assert second == 0

    def test_release_after_expiration_is_safe(self):
        lifecycle_service, queue_service, reservation_service = _services(default_ttl=timedelta(seconds=-1))
        task = _queued_task(lifecycle_service, queue_service)
        reservation_service.reserve(task.task_id, "worker-1")

        reservation_service.expire_stale_reservations()
        reservation_service.release(task.task_id, "worker-1")  # must not raise


class TestIsolation:
    def test_distinct_tasks_do_not_interfere(self):
        lifecycle_service, queue_service, reservation_service = _services()
        task_a = _queued_task(lifecycle_service, queue_service)
        task_b = _queued_task(lifecycle_service, queue_service)

        reservation_service.reserve(task_a.task_id, "worker-1")
        reservation_service.reserve(task_b.task_id, "worker-2")

        reservation_service.release(task_a.task_id, "worker-1")

        assert reservation_service.is_reservation_valid(task_a.task_id) is False
        assert reservation_service.is_reservation_valid(task_b.task_id) is True
