import pytest

from backend.session import (
    ExecutionStorageMigration,
    ExecutionStorageMigrationError as Error,
    ExecutionStorageMigrationService,
)


class _FakeFailoverService:
    def __init__(self):
        self._source_by_volume = {}
        self.registered = []

    def set_source(self, volume_id, target):
        self._source_by_volume[volume_id] = target

    def select(self, volume_id):
        return self._source_by_volume.get(volume_id)

    def register(self, volume_id, targets):
        targets = list(targets)
        self.registered.append((volume_id, targets))
        self._source_by_volume[volume_id] = targets[0]


class _FakeReplica:
    def __init__(self, replica_id, checksum):
        self.replica_id = replica_id
        self.checksum = checksum


class _FakeReplicaService:
    def __init__(self):
        self._checksum_by_id = {}
        self._counter = 0
        self.last_replica_id = None
        self.removed = []

    def replicate(self, volume_id, target):
        self._counter += 1
        replica_id = f"replica-{self._counter}"
        checksum = f"checksum-{volume_id}-{target}"
        self._checksum_by_id[replica_id] = checksum
        self.last_replica_id = replica_id

        return _FakeReplica(replica_id, checksum)

    def set_checksum(self, replica_id, checksum):
        self._checksum_by_id[replica_id] = checksum

    def verify(self, replica_id):
        if replica_id not in self._checksum_by_id:
            raise ValueError(f"unknown replica {replica_id!r}")

        return _FakeReplica(replica_id, self._checksum_by_id[replica_id])

    def remove(self, replica_id):
        self.removed.append(replica_id)
        self._checksum_by_id.pop(replica_id, None)


class _FakeCapacityService:
    def __init__(self):
        self._capacity = {}

    def set_capacity(self, destination, value):
        self._capacity[destination] = value

    def has_capacity(self, destination):
        return self._capacity.get(destination, True)


def _build():
    failover = _FakeFailoverService()
    replicas = _FakeReplicaService()
    capacity = _FakeCapacityService()
    service = ExecutionStorageMigrationService(failover, replicas, capacity)

    return failover, replicas, capacity, service


class TestExecutionStorageMigrationService:
    def test_start_verify_complete(self):
        failover, replicas, _, service = _build()
        failover.set_source("volume-1", "target-a")

        migration = service.start("volume-1", "target-b")

        assert isinstance(migration, ExecutionStorageMigration)
        assert migration.status == "IN_PROGRESS"
        assert migration.source_target == "target-a"
        assert migration.destination_target == "target-b"

        verified = service.verify(migration.migration_id)
        assert verified.status == "VERIFIED"

        completed = service.complete(migration.migration_id)

        assert completed.status == "COMPLETED"
        assert completed.completed_at is not None
        assert service.status(migration.migration_id) == "COMPLETED"
        assert failover.registered[-1] == ("volume-1", ["target-b", "target-a"])

    def test_destination_capacity_rejection(self):
        failover, _, capacity, service = _build()
        failover.set_source("volume-1", "target-a")
        capacity.set_capacity("target-b", False)

        with pytest.raises(Error):
            service.start("volume-1", "target-b")

    def test_checksum_mismatch(self):
        failover, replicas, _, service = _build()
        failover.set_source("volume-1", "target-a")

        migration = service.start("volume-1", "target-b")
        replicas.set_checksum(replicas.last_replica_id, "tampered-checksum")

        failed = service.verify(migration.migration_id)

        assert failed.status == "FAILED"

        with pytest.raises(Error):
            service.complete(migration.migration_id)

    def test_rollback(self):
        failover, replicas, _, service = _build()
        failover.set_source("volume-1", "target-a")

        migration = service.start("volume-1", "target-b")
        rolled_back = service.rollback(migration.migration_id)

        assert rolled_back.status == "ROLLED_BACK"
        assert replicas.removed == [replicas.last_replica_id]
        assert service.status(migration.migration_id) == "ROLLED_BACK"

        with pytest.raises(Error):
            service.rollback(migration.migration_id)

        failed_migration = service.start("volume-1", "target-c")
        replicas.set_checksum(replicas.last_replica_id, "tampered")
        service.verify(failed_migration.migration_id)

        rolled_back_after_failure = service.rollback(failed_migration.migration_id)
        assert rolled_back_after_failure.status == "ROLLED_BACK"

    def test_source_preservation(self):
        failover, _, _, service = _build()
        failover.set_source("volume-1", "target-a")

        migration = service.start("volume-1", "target-b")
        assert failover.select("volume-1") == "target-a"

        service.verify(migration.migration_id)
        assert failover.select("volume-1") == "target-a"

        service.complete(migration.migration_id)
        assert failover.select("volume-1") == "target-b"

    def test_status_transitions(self):
        failover, replicas, _, service = _build()
        failover.set_source("volume-1", "target-a")

        migration = service.start("volume-1", "target-b")
        assert service.status(migration.migration_id) == "IN_PROGRESS"

        service.verify(migration.migration_id)
        assert service.status(migration.migration_id) == "VERIFIED"

        service.complete(migration.migration_id)
        assert service.status(migration.migration_id) == "COMPLETED"

        other = service.start("volume-1", "target-c")
        replicas.set_checksum(replicas.last_replica_id, "tampered")
        service.verify(other.migration_id)
        assert service.status(other.migration_id) == "FAILED"
