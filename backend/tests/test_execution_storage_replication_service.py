import pytest

from backend.session import (
    ExecutionStorageReplica,
    ExecutionStorageReplicaError as Error,
    ExecutionStorageReplicationService,
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
    volume_service = _FakeVolumeService(status_by_volume or {"volume-1": "ATTACHED"})
    return volume_service, ExecutionStorageReplicationService(volume_service)


class TestExecutionStorageReplicationService:
    def test_create_replica(self):
        _, service = _build()

        replica = service.replicate("volume-1", "target-a")

        assert isinstance(replica, ExecutionStorageReplica)
        assert replica.volume_id == "volume-1"
        assert replica.target == "target-a"
        assert replica.status == "SYNCED"
        assert replica.checksum

    def test_source_volume_must_be_active(self):
        volume_service, service = _build()
        volume_service.set_status("volume-1", "AVAILABLE")

        with pytest.raises(Error):
            service.replicate("volume-1", "target-a")

    def test_duplicate_target_rejection(self):
        _, service = _build()
        service.replicate("volume-1", "target-a")

        with pytest.raises(Error):
            service.replicate("volume-1", "target-a")

    def test_checksum_verification(self):
        _, service = _build()
        replica = service.replicate("volume-1", "target-a")

        verified = service.verify(replica.replica_id)

        assert verified.checksum == replica.checksum

    def test_failed_sync(self):
        volume_service, service = _build()
        replica = service.replicate("volume-1", "target-a")

        volume_service.set_status("volume-1", "AVAILABLE")
        failed = service.sync(replica.replica_id)

        assert failed.status == "FAILED"
        assert failed.checksum == replica.checksum

        with pytest.raises(Error):
            service.verify(replica.replica_id)

    def test_retry(self):
        volume_service, service = _build()
        replica = service.replicate("volume-1", "target-a")

        volume_service.set_status("volume-1", "AVAILABLE")
        service.sync(replica.replica_id)

        volume_service.set_status("volume-1", "ATTACHED")
        recovered = service.sync(replica.replica_id)

        assert recovered.status == "SYNCED"
        service.verify(replica.replica_id)

    def test_replica_listing(self):
        volume_service, service = _build(
            status_by_volume={"volume-1": "ATTACHED", "volume-2": "ATTACHED"}
        )

        first = service.replicate("volume-1", "target-a")
        second = service.replicate("volume-1", "target-b")
        service.replicate("volume-2", "target-a")

        listing = service.replicas("volume-1")

        assert {replica.replica_id for replica in listing} == {first.replica_id, second.replica_id}
