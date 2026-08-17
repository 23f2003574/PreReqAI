import pytest

from backend.session import (
    ExecutionRuntimeResource,
    ExecutionRuntimeResourceError as Error,
    ExecutionRuntimeResourceService,
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

    def set_state(self, runtime_id, state):
        self._state_by_runtime[runtime_id] = state


def _build(state_by_runtime=None):
    state_service = _FakeStateService(
        state_by_runtime or {"runtime-1": "RUNNING", "runtime-2": "RUNNING"}
    )
    return state_service, ExecutionRuntimeResourceService(state_service)


class TestExecutionRuntimeResourceService:
    def test_allocate_and_release(self):
        _, service = _build()

        resource = service.allocate("runtime-1", "gpu", 2)

        assert isinstance(resource, ExecutionRuntimeResource)
        assert resource.status == "ALLOCATED"
        assert resource.released_at is None

        released = service.release(resource.resource_id)

        assert released.status == "RELEASED"
        assert released.released_at is not None
        assert service.active("runtime-1") == ()

    def test_release_is_idempotent(self):
        _, service = _build()
        resource = service.allocate("runtime-1", "gpu", 2)
        first = service.release(resource.resource_id)

        second = service.release(resource.resource_id)

        assert second.resource_id == first.resource_id
        assert second.released_at == first.released_at

    def test_allocation_requires_positive_amount(self):
        _, service = _build()

        with pytest.raises(Error):
            service.allocate("runtime-1", "gpu", 0)

        with pytest.raises(Error):
            service.allocate("runtime-1", "gpu", -1)

    def test_allocation_requires_active_runtime(self):
        _, service = _build(state_by_runtime={"runtime-1": "FAILED"})

        with pytest.raises(Error):
            service.allocate("runtime-1", "gpu", 2)

    def test_duplicate_allocation_creates_independent_claims(self):
        _, service = _build()

        first = service.allocate("runtime-1", "gpu", 2)
        second = service.allocate("runtime-1", "gpu", 2)

        assert first.resource_id != second.resource_id
        assert len(service.active("runtime-1")) == 2

    def test_release_all(self):
        _, service = _build()
        service.allocate("runtime-1", "gpu", 2)
        service.allocate("runtime-1", "memory", 4)

        released = service.release_all("runtime-1")

        assert len(released) == 2
        assert all(resource.status == "RELEASED" for resource in released)
        assert service.active("runtime-1") == ()

    def test_release_all_is_idempotent(self):
        _, service = _build()
        service.allocate("runtime-1", "gpu", 2)
        service.release_all("runtime-1")

        assert service.release_all("runtime-1") == ()

    def test_runtime_isolation(self):
        _, service = _build()
        service.allocate("runtime-1", "gpu", 2)
        service.allocate("runtime-2", "gpu", 4)

        assert len(service.active("runtime-1")) == 1
        assert len(service.active("runtime-2")) == 1
        assert service.active("runtime-1")[0].runtime_id == "runtime-1"
        assert service.active("runtime-2")[0].runtime_id == "runtime-2"

    def test_leaked_resource_detection(self):
        state_service, service = _build()
        resource = service.allocate("runtime-1", "gpu", 2)

        assert service.leaked() == ()

        state_service.set_state("runtime-1", "FAILED")

        leaked = service.leaked()

        assert len(leaked) == 1
        assert leaked[0].resource_id == resource.resource_id

    def test_terminal_cleanup(self):
        state_service, service = _build()
        service.allocate("runtime-1", "gpu", 2)
        state_service.set_state("runtime-1", "STOPPED")

        assert len(service.leaked()) == 1

        service.release_all("runtime-1")

        assert service.leaked() == ()

    def test_releasing_unknown_resource_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.release("does-not-exist")
