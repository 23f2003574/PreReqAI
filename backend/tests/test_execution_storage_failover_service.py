import pytest

from backend.session import (
    ExecutionStorageFailover,
    ExecutionStorageFailoverError as Error,
    ExecutionStorageFailoverService,
)


class _FakeReplica:
    def __init__(self, replica_id, target, status="SYNCED"):
        self.replica_id = replica_id
        self.target = target
        self.status = status


class _FakeReplicaService:
    def __init__(self):
        self._by_volume = {}

    def add(self, volume_id, replica_id, target, status="SYNCED"):
        self._by_volume.setdefault(volume_id, []).append(_FakeReplica(replica_id, target, status))

    def replicas(self, volume_id):
        return tuple(self._by_volume.get(volume_id, ()))


class _FakeCheck:
    def __init__(self, status):
        self.status = status


class _FakeIntegrityService:
    def __init__(self):
        self._status_by_replica = {}

    def set_status(self, replica_id, status):
        self._status_by_replica[replica_id] = status

    def check_replica(self, replica_id):
        return _FakeCheck(self._status_by_replica.get(replica_id, "OK"))


def _build():
    replicas = _FakeReplicaService()
    integrity = _FakeIntegrityService()
    return replicas, integrity, ExecutionStorageFailoverService(replicas, integrity)


class TestExecutionStorageFailoverService:
    def test_primary_selection(self):
        replicas, _, service = _build()
        replicas.add("volume-1", "replica-p", "target-primary")
        replicas.add("volume-1", "replica-b", "target-backup")

        failover = service.register("volume-1", ["target-primary", "target-backup"])

        assert isinstance(failover, ExecutionStorageFailover)
        assert failover.status == "PRIMARY"
        assert failover.selected_target == "target-primary"
        assert service.select("volume-1") == "target-primary"
        assert service.status("volume-1") == "PRIMARY"

    def test_replica_failover(self):
        replicas, _, service = _build()
        replicas.add("volume-1", "replica-p", "target-primary", status="FAILED")
        replicas.add("volume-1", "replica-b", "target-backup", status="SYNCED")

        failover = service.register("volume-1", ["target-primary", "target-backup"])

        assert failover.status == "FAILED_OVER"
        assert failover.selected_target == "target-backup"

    def test_corrupt_replica_skip(self):
        replicas, integrity, service = _build()
        replicas.add("volume-1", "replica-p", "target-primary", status="SYNCED")
        integrity.set_status("replica-p", "CORRUPT")
        replicas.add("volume-1", "replica-b", "target-backup", status="SYNCED")

        failover = service.register("volume-1", ["target-primary", "target-backup"])

        assert failover.status == "FAILED_OVER"
        assert failover.selected_target == "target-backup"

    def test_unavailable_target(self):
        replicas, _, service = _build()
        replicas.add("volume-1", "replica-b", "target-backup", status="SYNCED")

        failover = service.register("volume-1", ["target-primary", "target-backup"])

        assert failover.status == "FAILED_OVER"
        assert failover.selected_target == "target-backup"

    def test_all_targets_invalid(self):
        replicas, _, service = _build()
        replicas.add("volume-1", "replica-p", "target-primary", status="FAILED")
        replicas.add("volume-1", "replica-b", "target-backup", status="FAILED")

        failover = service.register("volume-1", ["target-primary", "target-backup"])

        assert failover.status == "UNAVAILABLE"
        assert failover.selected_target is None
        assert service.status("volume-1") == "UNAVAILABLE"

    def test_deterministic_selection(self):
        replicas, _, service = _build()
        replicas.add("volume-1", "replica-p", "target-primary", status="FAILED")
        replicas.add("volume-1", "replica-b1", "target-backup-1", status="SYNCED")
        replicas.add("volume-1", "replica-b2", "target-backup-2", status="SYNCED")

        service.register("volume-1", ["target-primary", "target-backup-1", "target-backup-2"])

        first = service.execute("volume-1")
        second = service.execute("volume-1")

        assert first.selected_target == "target-backup-1"
        assert second.selected_target == "target-backup-1"
