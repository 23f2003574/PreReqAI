import pytest

from backend.session import (
    ExecutionStorageVolume,
    ExecutionStorageVolumeError as Error,
    ExecutionStorageVolumeService,
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
    return state_service, ExecutionStorageVolumeService(state_service)


class TestExecutionStorageVolumeService:
    def test_create_attach_detach(self):
        _, service = _build()

        volume = service.create("scope-1", 100)

        assert isinstance(volume, ExecutionStorageVolume)
        assert volume.status == "AVAILABLE"
        assert service.status(volume.volume_id) == "AVAILABLE"

        attached = service.attach(volume.volume_id, "runtime-1")

        assert attached.status == "ATTACHED"
        assert service.status(volume.volume_id) == "ATTACHED"

        detached = service.detach(volume.volume_id, "runtime-1")

        assert detached.status == "AVAILABLE"
        assert service.status(volume.volume_id) == "AVAILABLE"

    def test_invalid_size(self):
        _, service = _build()

        with pytest.raises(Error):
            service.create("scope-1", 0)

        with pytest.raises(Error):
            service.create("scope-1", -5)

    def test_duplicate_attachment(self):
        _, service = _build()

        volume = service.create("scope-1", 100)
        service.attach(volume.volume_id, "runtime-1")

        with pytest.raises(Error):
            service.attach(volume.volume_id, "runtime-2")

    def test_terminal_runtime_rejection(self):
        state_service, service = _build()
        state_service.set_state("runtime-1", "STOPPED")

        volume = service.create("scope-1", 100)

        with pytest.raises(Error):
            service.attach(volume.volume_id, "runtime-1")

    def test_active_lookup(self):
        _, service = _build()

        first = service.create("scope-1", 50)
        second = service.create("scope-1", 75)
        service.attach(first.volume_id, "runtime-1")
        service.attach(second.volume_id, "runtime-2")

        active = service.active("runtime-1")

        assert {volume.volume_id for volume in active} == {first.volume_id}

    def test_attached_volume_protection(self):
        _, service = _build()

        volume = service.create("scope-1", 100)
        service.attach(volume.volume_id, "runtime-1")

        with pytest.raises(Error):
            service.delete(volume.volume_id)

        service.detach(volume.volume_id, "runtime-1")

        service.delete(volume.volume_id)

        with pytest.raises(Error):
            service.status(volume.volume_id)
