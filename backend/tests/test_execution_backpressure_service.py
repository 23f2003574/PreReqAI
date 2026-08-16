import pytest

from backend.session import (
    ExecutionBackpressureError as Error,
    ExecutionBackpressureService,
    ExecutionBackpressureState,
)


def _build():
    return ExecutionBackpressureService()


class TestExecutionBackpressureService:
    def test_configure_limit(self):
        service = _build()

        state = service.configure("scope-1", 2)

        assert isinstance(state, ExecutionBackpressureState)
        assert state.scope_id == "scope-1"
        assert state.max_queue == 2
        assert state.current_queue == 0
        assert state.status == "NORMAL"

    def test_invalid_limit_is_rejected(self):
        service = _build()

        with pytest.raises(Error):
            service.configure("scope-1", 0)

    def test_enqueue_within_capacity(self):
        service = _build()
        service.configure("scope-1", 2)

        assert service.can_enqueue("scope-1") is True

        state = service.record_enqueue("scope-1")

        assert state.current_queue == 1
        assert state.status == "NORMAL"
        assert service.can_enqueue("scope-1") is True

    def test_capacity_rejection(self):
        service = _build()
        service.configure("scope-1", 1)
        service.record_enqueue("scope-1")

        assert service.can_enqueue("scope-1") is False
        assert service.status("scope-1") == "SATURATED"

        with pytest.raises(Error):
            service.record_enqueue("scope-1")

    def test_dequeue_recovery(self):
        service = _build()
        service.configure("scope-1", 1)
        service.record_enqueue("scope-1")

        state = service.record_dequeue("scope-1")

        assert state.current_queue == 0
        assert state.status == "NORMAL"
        assert service.can_enqueue("scope-1") is True

        service.record_enqueue("scope-1")

        assert service.status("scope-1") == "SATURATED"

    def test_dequeue_on_empty_queue_is_rejected(self):
        service = _build()
        service.configure("scope-1", 1)

        with pytest.raises(Error):
            service.record_dequeue("scope-1")

    def test_scope_isolation(self):
        service = _build()
        service.configure("scope-1", 1)
        service.configure("scope-2", 1)

        service.record_enqueue("scope-1")

        assert service.can_enqueue("scope-1") is False
        assert service.can_enqueue("scope-2") is True

    def test_operations_on_unconfigured_scope_are_rejected(self):
        service = _build()

        with pytest.raises(Error):
            service.can_enqueue("scope-1")

        with pytest.raises(Error):
            service.record_enqueue("scope-1")

        with pytest.raises(Error):
            service.status("scope-1")

    def test_reconfiguring_preserves_current_queue(self):
        service = _build()
        service.configure("scope-1", 2)
        service.record_enqueue("scope-1")

        state = service.configure("scope-1", 3)

        assert state.current_queue == 1
        assert state.max_queue == 3
        assert state.status == "NORMAL"

    def test_reconfiguring_below_current_queue_is_rejected(self):
        service = _build()
        service.configure("scope-1", 2)
        service.record_enqueue("scope-1")
        service.record_enqueue("scope-1")

        with pytest.raises(Error):
            service.configure("scope-1", 1)
