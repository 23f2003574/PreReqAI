import dataclasses

import pytest

from backend.session import (
    ExecutionStorageSnapshot,
    ExecutionStorageSnapshotError as Error,
    ExecutionStorageSnapshotService,
)


class _FakeVolume:
    def __init__(self, volume_id, status, size):
        self.volume_id = volume_id
        self.status = status
        self.size = size


class _FakeVolumeService:
    def __init__(self):
        self._volumes = {}

    def add(self, volume_id, status="ATTACHED", size=100):
        self._volumes[volume_id] = _FakeVolume(volume_id, status, size)

    def set_status(self, volume_id, status):
        existing = self._volumes[volume_id]
        self._volumes[volume_id] = _FakeVolume(volume_id, status, existing.size)

    def get(self, volume_id):
        if volume_id not in self._volumes:
            raise ValueError(f"unknown volume {volume_id!r}")

        return self._volumes[volume_id]


def _build():
    volume_service = _FakeVolumeService()
    return volume_service, ExecutionStorageSnapshotService(volume_service)


class TestExecutionStorageSnapshotService:
    def test_create_snapshot(self):
        volume_service, service = _build()
        volume_service.add("volume-1", status="ATTACHED", size=100)

        snapshot = service.create("volume-1")

        assert isinstance(snapshot, ExecutionStorageSnapshot)
        assert snapshot.volume_id == "volume-1"
        assert snapshot.size == 100
        assert service.get(snapshot.snapshot_id) == snapshot

    def test_only_attached_volumes_can_snapshot(self):
        volume_service, service = _build()
        volume_service.add("volume-1", status="AVAILABLE", size=100)

        with pytest.raises(Error):
            service.create("volume-1")

    def test_checksum_generation(self):
        volume_service, service = _build()
        volume_service.add("volume-1", status="ATTACHED", size=100)
        volume_service.add("volume-2", status="ATTACHED", size=200)

        first = service.create("volume-1")
        second = service.create("volume-2")

        assert first.checksum
        assert isinstance(first.checksum, str)
        assert first.checksum != second.checksum

    def test_immutable_snapshot(self):
        volume_service, service = _build()
        volume_service.add("volume-1", status="ATTACHED", size=100)

        snapshot = service.create("volume-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            snapshot.size = 999

    def test_restore(self):
        volume_service, service = _build()
        volume_service.add("volume-1", status="ATTACHED", size=100)
        volume_service.add("volume-2", status="AVAILABLE", size=100)

        snapshot = service.create("volume-1")

        restored = service.restore(snapshot.snapshot_id, "volume-2")

        assert restored == snapshot

    def test_incompatible_restore(self):
        volume_service, service = _build()
        volume_service.add("volume-1", status="ATTACHED", size=100)
        volume_service.add("volume-2", status="AVAILABLE", size=50)

        snapshot = service.create("volume-1")

        with pytest.raises(Error):
            service.restore(snapshot.snapshot_id, "volume-2")

    def test_snapshot_history(self):
        volume_service, service = _build()
        volume_service.add("volume-1", status="ATTACHED", size=100)

        first = service.create("volume-1")
        second = service.create("volume-1")

        history = service.history("volume-1")

        assert history == (first, second)
