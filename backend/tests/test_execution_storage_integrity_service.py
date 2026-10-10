import pytest

from backend.session import (
    ExecutionStorageIntegrityCheck,
    ExecutionStorageIntegrityCheckError as Error,
    ExecutionStorageIntegrityService,
)


class _FakeVolumeChecksums:
    def __init__(self):
        self._expected = {}
        self._actual = {}

    def set_expected(self, volume_id, checksum):
        self._expected[volume_id] = checksum

    def set_actual(self, volume_id, checksum):
        self._actual[volume_id] = checksum

    def expected_checksum(self, volume_id):
        if volume_id not in self._expected:
            raise ValueError(f"unknown volume {volume_id!r}")

        return self._expected[volume_id]

    def actual_checksum(self, volume_id):
        if volume_id not in self._actual:
            raise ValueError(f"unknown volume {volume_id!r}")

        return self._actual[volume_id]


class _FakeReplica:
    def __init__(self, replica_id, volume_id, target, checksum, status="SYNCED"):
        self.replica_id = replica_id
        self.volume_id = volume_id
        self.target = target
        self.checksum = checksum
        self.status = status


class _FakeReplicaService:
    def __init__(self):
        self._replicas = {}
        self._sync_overrides = {}

    def add(self, replica_id, volume_id, target, checksum, status="SYNCED"):
        self._replicas[replica_id] = _FakeReplica(replica_id, volume_id, target, checksum, status)

    def get(self, replica_id):
        if replica_id not in self._replicas:
            raise ValueError(f"unknown replica {replica_id!r}")

        return self._replicas[replica_id]

    def set_sync_result(self, replica_id, checksum, status="SYNCED"):
        self._sync_overrides[replica_id] = (checksum, status)

    def sync(self, replica_id):
        replica = self.get(replica_id)

        if replica_id in self._sync_overrides:
            checksum, status = self._sync_overrides[replica_id]
            replica = _FakeReplica(replica_id, replica.volume_id, replica.target, checksum, status)
            self._replicas[replica_id] = replica

        return replica


def _build():
    volumes = _FakeVolumeChecksums()
    replicas = _FakeReplicaService()
    return volumes, replicas, ExecutionStorageIntegrityService(volumes, replicas)


class TestExecutionStorageIntegrityService:
    def test_matching_checksum(self):
        volumes, _, service = _build()
        volumes.set_expected("volume-1", "abc")
        volumes.set_actual("volume-1", "abc")

        check = service.check("volume-1")

        assert isinstance(check, ExecutionStorageIntegrityCheck)
        assert check.status == "OK"
        assert check.target == "PRIMARY"

    def test_corruption_detection(self):
        volumes, _, service = _build()
        volumes.set_expected("volume-1", "abc")
        volumes.set_actual("volume-1", "xyz")

        check = service.check("volume-1")

        assert check.status == "CORRUPT"
        assert check.expected_checksum == "abc"
        assert check.actual_checksum == "xyz"

    def test_replica_verification(self):
        volumes, replicas, service = _build()
        volumes.set_expected("volume-1", "abc")
        replicas.add("replica-1", "volume-1", "target-a", "abc")
        replicas.add("replica-2", "volume-1", "target-b", "different")

        ok = service.check_replica("replica-1")
        corrupt = service.check_replica("replica-2")

        assert ok.status == "OK"
        assert ok.target == "target-a"
        assert corrupt.status == "CORRUPT"
        assert corrupt.target == "target-b"

    def test_invalid_repair_source(self):
        volumes, replicas, service = _build()
        volumes.set_expected("volume-1", "abc")
        replicas.add("replica-1", "volume-1", "target-a", "stale")

        with pytest.raises(Error):
            service.repair("replica-1")

        volumes.set_actual("volume-1", "different")
        service.check("volume-1")

        with pytest.raises(Error):
            service.repair("replica-1")

    def test_successful_repair(self):
        volumes, replicas, service = _build()
        volumes.set_expected("volume-1", "abc")
        volumes.set_actual("volume-1", "abc")
        service.check("volume-1")

        replicas.add("replica-1", "volume-1", "target-a", "stale")
        corrupt = service.check_replica("replica-1")
        assert corrupt.status == "CORRUPT"

        replicas.set_sync_result("replica-1", "abc", status="SYNCED")
        repaired = service.repair("replica-1")

        assert repaired.status == "OK"
        assert repaired.actual_checksum == "abc"

    def test_history_ordering(self):
        volumes, _, service = _build()
        volumes.set_expected("volume-1", "abc")
        volumes.set_actual("volume-1", "abc")
        first = service.check("volume-1")

        volumes.set_actual("volume-1", "xyz")
        second = service.check("volume-1")

        assert service.history("volume-1") == (first, second)
