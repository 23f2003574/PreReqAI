import pytest

from backend.session import (
    ExecutionStorageGarbageRecord,
    ExecutionStorageGarbageRecordError as Error,
    ExecutionStorageGarbageCollectionService,
)


class _FakeVolume:
    def __init__(self, volume_id, status):
        self.volume_id = volume_id
        self.status = status


class _FakeVolumeService:
    def __init__(self):
        self._status_by_volume = {}
        self._scope_by_volume = {}
        self._volumes_by_scope = {}

    def add(self, volume_id, scope_id, status="AVAILABLE"):
        self._status_by_volume[volume_id] = status
        self._scope_by_volume[volume_id] = scope_id
        self._volumes_by_scope.setdefault(scope_id, []).append(volume_id)

    def set_status(self, volume_id, status):
        self._status_by_volume[volume_id] = status

    def status(self, volume_id):
        if volume_id not in self._status_by_volume:
            raise ValueError(f"unknown volume {volume_id!r}")

        return self._status_by_volume[volume_id]

    def for_scope(self, scope_id):
        return tuple(
            _FakeVolume(volume_id, self._status_by_volume[volume_id])
            for volume_id in self._volumes_by_scope.get(scope_id, [])
        )

    def scope_of(self, volume_id):
        if volume_id not in self._scope_by_volume:
            raise ValueError(f"unknown volume {volume_id!r}")

        return self._scope_by_volume[volume_id]


class _FakeMountService:
    def __init__(self):
        self._mounts_by_volume = {}

    def add_mount(self, volume_id, mount_id="mount-1"):
        self._mounts_by_volume.setdefault(volume_id, []).append(mount_id)

    def volume_mounts(self, volume_id):
        return tuple(self._mounts_by_volume.get(volume_id, ()))


class _FakeSnapshot:
    def __init__(self, snapshot_id, volume_id):
        self.snapshot_id = snapshot_id
        self.volume_id = volume_id


class _FakeSnapshotService:
    def __init__(self):
        self._snapshots_by_id = {}
        self._by_volume = {}

    def add(self, snapshot_id, volume_id):
        snapshot = _FakeSnapshot(snapshot_id, volume_id)
        self._snapshots_by_id[snapshot_id] = snapshot
        self._by_volume.setdefault(volume_id, []).append(snapshot)

    def history(self, volume_id):
        return tuple(self._by_volume.get(volume_id, ()))

    def get(self, snapshot_id):
        if snapshot_id not in self._snapshots_by_id:
            raise ValueError(f"unknown snapshot {snapshot_id!r}")

        return self._snapshots_by_id[snapshot_id]


class _FakeReplica:
    def __init__(self, replica_id, volume_id):
        self.replica_id = replica_id
        self.volume_id = volume_id


class _FakeReplicaService:
    def __init__(self):
        self._replicas_by_id = {}
        self._by_volume = {}

    def add(self, replica_id, volume_id):
        replica = _FakeReplica(replica_id, volume_id)
        self._replicas_by_id[replica_id] = replica
        self._by_volume.setdefault(volume_id, []).append(replica)

    def replicas(self, volume_id):
        return tuple(self._by_volume.get(volume_id, ()))

    def get(self, replica_id):
        if replica_id not in self._replicas_by_id:
            raise ValueError(f"unknown replica {replica_id!r}")

        return self._replicas_by_id[replica_id]


def _build(retention_seconds=0):
    volumes = _FakeVolumeService()
    mounts = _FakeMountService()
    snapshots = _FakeSnapshotService()
    replicas = _FakeReplicaService()
    service = ExecutionStorageGarbageCollectionService(
        volumes, mounts, snapshots, replicas, retention_seconds=retention_seconds
    )
    return volumes, mounts, snapshots, replicas, service


class TestExecutionStorageGarbageCollectionService:
    def test_scan_unused_resources(self):
        volumes, _, snapshots, replicas, service = _build()
        volumes.add("volume-1", "scope-1", status="AVAILABLE")
        snapshots.add("snapshot-1", "volume-1")
        replicas.add("replica-1", "volume-1")

        marked = service.scan("scope-1")

        assert len(marked) == 3
        assert all(isinstance(record, ExecutionStorageGarbageRecord) for record in marked)
        assert {record.resource_type for record in marked} == {"VOLUME", "SNAPSHOT", "REPLICA"}
        assert {record.resource_id for record in marked} == {"volume-1", "snapshot-1", "replica-1"}

    def test_active_resource_protection(self):
        volumes, mounts, _, _, service = _build()
        volumes.add("volume-1", "scope-1", status="ATTACHED")
        volumes.add("volume-2", "scope-1", status="AVAILABLE")
        mounts.add_mount("volume-2")

        assert service.scan("scope-1") == ()
        assert service.protected("volume-1") is True
        assert service.protected("volume-2") is True

        with pytest.raises(Error):
            service.mark("volume-1")

        with pytest.raises(Error):
            service.mark("volume-2")

    def test_retention_handling(self):
        volumes, _, _, _, service = _build(retention_seconds=3600)
        volumes.add("volume-1", "scope-1", status="AVAILABLE")

        record = service.mark("volume-1")
        collected = service.collect("scope-1")

        assert collected == ()
        assert service.history("scope-1") == (record,)

    def test_mark_collect(self):
        volumes, _, _, _, service = _build(retention_seconds=0)
        volumes.add("volume-1", "scope-1", status="AVAILABLE")

        record = service.mark("volume-1")
        assert record.deleted_at is None

        again = service.mark("volume-1")
        assert again.record_id == record.record_id

        collected = service.collect("scope-1")

        assert len(collected) == 1
        assert collected[0].record_id == record.record_id
        assert collected[0].deleted_at is not None

    def test_repeated_collection(self):
        volumes, _, _, _, service = _build(retention_seconds=0)
        volumes.add("volume-1", "scope-1", status="AVAILABLE")
        service.mark("volume-1")

        first = service.collect("scope-1")
        second = service.collect("scope-1")

        assert len(first) == 1
        assert second == ()

    def test_collection_history(self):
        volumes, _, _, _, service = _build(retention_seconds=0)
        volumes.add("volume-1", "scope-1", status="AVAILABLE")
        volumes.add("volume-2", "scope-1", status="AVAILABLE")

        first = service.mark("volume-1")
        second = service.mark("volume-2")

        history = service.history("scope-1")

        assert history == (first, second)
