import pytest

from backend.session import (
    ExecutionSchedulerFailover,
    ExecutionSchedulerFailoverError as Error,
    ExecutionSchedulerFailoverService,
)


class _FakeAvailabilityService:
    def __init__(self, available=None):
        self._unavailable = set()
        self._available = set(available or ())

    def is_available(self, scheduler_id):
        if scheduler_id in self._unavailable:
            return False

        return True

    def mark_unavailable(self, scheduler_id):
        self._unavailable.add(scheduler_id)

    def mark_available(self, scheduler_id):
        self._unavailable.discard(scheduler_id)


def _build():
    availability = _FakeAvailabilityService()
    return availability, ExecutionSchedulerFailoverService(availability)


class TestExecutionSchedulerFailoverService:
    def test_primary_selection(self):
        _, service = _build()

        state = service.register("scope-1", ["scheduler-a", "scheduler-b", "scheduler-c"])

        assert isinstance(state, ExecutionSchedulerFailover)
        assert state.selected_scheduler == "scheduler-a"
        assert state.status == "ACTIVE"

    def test_backup_failover(self):
        availability, service = _build()
        service.register("scope-1", ["scheduler-a", "scheduler-b", "scheduler-c"])

        availability.mark_unavailable("scheduler-a")
        state = service.execute("scope-1")

        assert state.selected_scheduler == "scheduler-b"
        assert state.status == "ACTIVE"

    def test_unavailable_scheduler_is_skipped(self):
        availability, service = _build()
        availability.mark_unavailable("scheduler-a")
        availability.mark_unavailable("scheduler-b")

        state = service.register("scope-1", ["scheduler-a", "scheduler-b", "scheduler-c"])

        assert state.selected_scheduler == "scheduler-c"

    def test_all_unavailable(self):
        availability, service = _build()
        availability.mark_unavailable("scheduler-a")
        availability.mark_unavailable("scheduler-b")

        state = service.register("scope-1", ["scheduler-a", "scheduler-b"])

        assert state.selected_scheduler is None
        assert state.status == "FAILED"

    def test_recovers_once_a_scheduler_becomes_available(self):
        availability, service = _build()
        availability.mark_unavailable("scheduler-a")
        availability.mark_unavailable("scheduler-b")
        service.register("scope-1", ["scheduler-a", "scheduler-b"])

        availability.mark_available("scheduler-a")
        state = service.execute("scope-1")

        assert state.selected_scheduler == "scheduler-a"
        assert state.status == "ACTIVE"

    def test_current_scheduler_state_is_preserved(self):
        availability, service = _build()
        service.register("scope-1", ["scheduler-a", "scheduler-b"])

        availability.mark_unavailable("scheduler-a")
        service.execute("scope-1")
        availability.mark_available("scheduler-a")
        state = service.execute("scope-1")

        assert state.selected_scheduler == "scheduler-b"

    def test_deterministic_selection(self):
        _, service = _build()
        service.register("scope-1", ["scheduler-a", "scheduler-b", "scheduler-c"])

        first = service.execute("scope-1")
        second = service.execute("scope-1")

        assert first.selected_scheduler == second.selected_scheduler == "scheduler-a"

    def test_status_lookup(self):
        _, service = _build()
        service.register("scope-1", ["scheduler-a"])

        assert service.status("scope-1") == "ACTIVE"
        assert service.select("scope-1") == "scheduler-a"

    def test_status_on_unregistered_scope_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.status("scope-1")

    def test_register_with_empty_schedulers_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.register("scope-1", [])

    def test_register_with_duplicate_schedulers_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.register("scope-1", ["scheduler-a", "scheduler-a"])
