import pytest

from backend.session import (
    ExecutionRuntimeCancellation,
    ExecutionRuntimeCancellationError as Error,
    ExecutionRuntimeCancellationService,
    ExecutionRuntimePauseError,
    ExecutionRuntimePauseService,
)


class _FakeStateRecord:
    def __init__(self, state):
        self.state = state


class _FakeStateService:
    def __init__(self, state_by_runtime=None):
        self._state_by_runtime = dict(state_by_runtime or {})

    def state(self, runtime_id):
        if runtime_id not in self._state_by_runtime:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return _FakeStateRecord(self._state_by_runtime[runtime_id])

    def transition(self, runtime_id, state, reason):
        if runtime_id not in self._state_by_runtime:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        self._state_by_runtime[runtime_id] = state

        return _FakeStateRecord(state)


def _build(state_by_runtime=None):
    state_service = _FakeStateService(state_by_runtime or {"runtime-1": "RUNNING"})
    return state_service, ExecutionRuntimeCancellationService(state_service)


class TestExecutionRuntimeCancellationService:
    def test_request_and_cancel(self):
        state_service, service = _build()

        requested = service.request("runtime-1", "operator requested shutdown")

        assert isinstance(requested, ExecutionRuntimeCancellation)
        assert requested.completed_at is None
        assert state_service.state("runtime-1").state == "STOPPING"
        assert service.status("runtime-1") == "STOPPING"

        completed = service.cancel("runtime-1")

        assert completed.cancellation_id == requested.cancellation_id
        assert completed.completed_at is not None
        assert state_service.state("runtime-1").state == "STOPPED"
        assert service.status("runtime-1") == "STOPPED"

    def test_duplicate_cancellation_is_idempotent(self):
        _, service = _build()
        service.request("runtime-1", "operator requested shutdown")
        first = service.cancel("runtime-1")

        second = service.cancel("runtime-1")

        assert second.cancellation_id == first.cancellation_id
        assert second.completed_at == first.completed_at

    def test_cancel_without_request_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.cancel("runtime-1")

    def test_terminal_runtime_rejection(self):
        _, service = _build(state_by_runtime={"runtime-1": "FAILED"})

        with pytest.raises(Error):
            service.request("runtime-1", "attempt cancel")

    def test_paused_runtime_can_be_cancelled(self):
        state_service, service = _build(state_by_runtime={"runtime-1": "PAUSED"})

        service.request("runtime-1", "operator requested shutdown")

        assert state_service.state("runtime-1").state == "STOPPING"

    def test_history(self):
        _, service = _build()
        requested = service.request("runtime-1", "operator requested shutdown")
        completed = service.cancel("runtime-1")

        history = service.history("runtime-1")

        assert len(history) == 1
        assert history[0].cancellation_id == requested.cancellation_id
        assert history[0].completed_at == completed.completed_at

    def test_history_for_unknown_runtime_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.history("does-not-exist")

    def test_reason_preservation(self):
        _, service = _build()
        service.request("runtime-1", "resource exhaustion detected")

        history = service.history("runtime-1")

        assert history[0].reason == "resource exhaustion detected"

    def test_resume_after_cancel_rejection(self):
        state_service, cancellation_service = _build()
        pause_service = ExecutionRuntimePauseService(state_service)

        cancellation_service.request("runtime-1", "operator requested shutdown")
        cancellation_service.cancel("runtime-1")

        with pytest.raises(ExecutionRuntimePauseError):
            pause_service.resume("runtime-1")
