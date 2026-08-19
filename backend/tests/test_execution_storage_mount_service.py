import pytest

from backend.session import (
    ExecutionStorageMount,
    ExecutionStorageMountError as Error,
    ExecutionStorageMountService,
)


class _FakeVolumeService:
    def __init__(self, status_by_volume=None):
        self._status_by_volume = dict(status_by_volume or {})

    def status(self, volume_id):
        if volume_id not in self._status_by_volume:
            raise ValueError(f"unknown volume {volume_id!r}")

        return self._status_by_volume[volume_id]

    def set_status(self, volume_id, status):
        self._status_by_volume[volume_id] = status


def _build(status_by_volume=None):
    volume_service = _FakeVolumeService(
        status_by_volume or {"volume-1": "AVAILABLE", "volume-2": "AVAILABLE"}
    )
    return volume_service, ExecutionStorageMountService(volume_service)


class TestExecutionStorageMountService:
    def test_mount_unmount(self):
        _, service = _build()

        mount = service.mount("volume-1", "runtime-1", "/mnt/data", "READ_WRITE")

        assert isinstance(mount, ExecutionStorageMount)
        assert mount.volume_id == "volume-1"
        assert mount.runtime_id == "runtime-1"
        assert mount in service.active("runtime-1")

        unmounted = service.unmount(mount.mount_id)

        assert unmounted.mount_id == mount.mount_id
        assert service.active("runtime-1") == ()

        with pytest.raises(Error):
            service.unmount(mount.mount_id)

    def test_mode_enforcement(self):
        _, service = _build()

        read_only = service.mount("volume-1", "runtime-1", "/mnt/ro", "READ_ONLY")
        read_write = service.mount("volume-2", "runtime-1", "/mnt/rw", "READ_WRITE")

        with pytest.raises(Error):
            service.write(read_only.mount_id)

        service.write(read_write.mount_id)

        with pytest.raises(Error):
            service.mount("volume-1", "runtime-2", "/mnt/x", "APPEND")

    def test_duplicate_path(self):
        _, service = _build()

        service.mount("volume-1", "runtime-1", "/mnt/data", "READ_ONLY")

        with pytest.raises(Error):
            service.mount("volume-2", "runtime-1", "/mnt/data", "READ_ONLY")

    def test_unavailable_volume(self):
        volume_service, service = _build()
        volume_service.set_status("volume-1", "ATTACHED")

        with pytest.raises(Error):
            service.mount("volume-1", "runtime-1", "/mnt/data", "READ_ONLY")

    def test_runtime_isolation(self):
        _, service = _build()

        first = service.mount("volume-1", "runtime-1", "/mnt/data", "READ_ONLY")
        second = service.mount("volume-2", "runtime-2", "/mnt/data", "READ_ONLY")

        assert {mount.mount_id for mount in service.active("runtime-1")} == {first.mount_id}
        assert {mount.mount_id for mount in service.active("runtime-2")} == {second.mount_id}

    def test_volume_mount_lookup(self):
        volume_service, service = _build(
            {"volume-1": "AVAILABLE", "volume-2": "AVAILABLE"}
        )

        first = service.mount("volume-1", "runtime-1", "/mnt/a", "READ_ONLY")
        service.mount("volume-2", "runtime-1", "/mnt/b", "READ_ONLY")

        volume_service.set_status("volume-1", "ATTACHED")

        assert {mount.mount_id for mount in service.volume_mounts("volume-1")} == {first.mount_id}
