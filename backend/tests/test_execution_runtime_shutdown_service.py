import pytest

from backend.session import (
    ExecutionRuntimeShutdown,
    ExecutionRuntimeShutdownError as Error,
    ExecutionRuntimeShutdownService,
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


class _FakeResourceService:
    def __init__(self):
        self.released = []

    def release(self, runtime_id):
        self.released.append(runtime_id)


def _build(state_by_runtime=None):
    state_service = _FakeStateService(state_by_runtime or {"runtime-1": "RUNNING"})
    resource_service = _FakeResourceService()
    return state_service, resource_service, ExecutionRuntimeShutdownService(
        state_service, resource_service
    )


class TestExecutionRuntimeShutdownService:
    def test_request_and_shutdown(self):
        state_service, _, service = _build()

        requested = service.request("runtime-1", "operator requested shutdown")

        assert isinstance(requested, ExecutionRuntimeShutdown)
        assert requested.status == "STOPPING"
        assert requested.completed_at is None

        completed = service.shutdown("runtime-1")

        assert completed.shutdown_id == requested.shutdown_id
        assert completed.status == "STOPPED"
        assert completed.completed_at is not None
        assert state_service.state("runtime-1").state == "STOPPED"

    def test_state_transitions(self):
        state_service, _, service = _build()

        service.request("runtime-1", "operator requested shutdown")
        assert state_service.state("runtime-1").state == "STOPPING"
        assert service.status("runtime-1") == "STOPPING"

        service.shutdown("runtime-1")
        assert state_service.state("runtime-1").state == "STOPPED"
        assert service.status("runtime-1") == "STOPPED"

    def test_resource_release(self):
        _, resource_service, service = _build()
        service.request("runtime-1", "operator requested shutdown")

        assert resource_service.released == []

        service.shutdown("runtime-1")

        assert resource_service.released == ["runtime-1"]

    def test_duplicate_shutdown_is_idempotent(self):
        _, resource_service, service = _build()
        service.request("runtime-1", "operator requested shutdown")
        first = service.shutdown("runtime-1")

        second = service.shutdown("runtime-1")

        assert second.shutdown_id == first.shutdown_id
        assert second.completed_at == first.completed_at
        assert resource_service.released == ["runtime-1"]

    def test_terminal_runtime_rejection(self):
        _, _, service = _build(state_by_runtime={"runtime-1": "FAILED"})

        with pytest.raises(Error):
            service.request("runtime-1", "attempt shutdown")

    def test_shutdown_without_request_is_rejected(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.shutdown("runtime-1")

    def test_history(self):
        _, _, service = _build()
        requested = service.request("runtime-1", "operator requested shutdown")
        completed = service.shutdown("runtime-1")

        history = service.history("runtime-1")

        assert len(history) == 1
        assert history[0].shutdown_id == requested.shutdown_id
        assert history[0].completed_at == completed.completed_at

    def test_history_for_unknown_runtime_is_rejected(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.history("does-not-exist")
