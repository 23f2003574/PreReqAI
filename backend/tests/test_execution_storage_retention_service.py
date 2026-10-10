import pytest

from backend.session import (
    ExecutionStorageRetentionPolicy,
    ExecutionStorageRetentionPolicyError as Error,
    ExecutionStorageRetentionService,
)


class _FakeGCService:
    def __init__(self):
        self._protected = {}

    def set_protected(self, resource_id, value):
        self._protected[resource_id] = value

    def protected(self, resource_id):
        return self._protected.get(resource_id, False)


class _FakeVolumeService:
    def __init__(self):
        self._status_by_volume = {}
        self._scope_by_volume = {}

    def add(self, volume_id, scope_id, status="AVAILABLE"):
        self._status_by_volume[volume_id] = status
        self._scope_by_volume[volume_id] = scope_id

    def status(self, volume_id):
        if volume_id not in self._status_by_volume:
            raise ValueError(f"unknown volume {volume_id!r}")

        return self._status_by_volume[volume_id]

    def scope_of(self, volume_id):
        if volume_id not in self._scope_by_volume:
            raise ValueError(f"unknown volume {volume_id!r}")

        return self._scope_by_volume[volume_id]


class _FakeLinked:
    def __init__(self, volume_id):
        self.volume_id = volume_id


class _FakeLinkedService:
    def __init__(self):
        self._by_id = {}

    def add(self, resource_id, volume_id):
        self._by_id[resource_id] = _FakeLinked(volume_id)

    def get(self, resource_id):
        if resource_id not in self._by_id:
            raise ValueError(f"unknown resource {resource_id!r}")

        return self._by_id[resource_id]


def _build():
    gc = _FakeGCService()
    volumes = _FakeVolumeService()
    snapshots = _FakeLinkedService()
    replicas = _FakeLinkedService()
    service = ExecutionStorageRetentionService(gc, volumes, snapshots, replicas)
    return gc, volumes, snapshots, replicas, service


class TestExecutionStorageRetentionService:
    def test_configure_policy(self):
        _, _, _, _, service = _build()

        policy = service.configure("scope-1", "VOLUME", 3600)

        assert isinstance(policy, ExecutionStorageRetentionPolicy)
        assert policy.scope_id == "scope-1"
        assert policy.resource_type == "VOLUME"
        assert policy.retention_seconds == 3600
        assert policy.enabled is True
        assert service.policy("scope-1", "VOLUME") == policy

    def test_retention_eligibility(self):
        gc, volumes, _, _, service = _build()
        volumes.add("volume-1", "scope-1", status="AVAILABLE")

        assert service.eligible("volume-1") is False

        service.configure("scope-1", "VOLUME", 3600)

        assert service.eligible("volume-1") is True

    def test_active_resource_protection(self):
        gc, volumes, _, _, service = _build()
        volumes.add("volume-1", "scope-1", status="ATTACHED")
        service.configure("scope-1", "VOLUME", 3600)
        gc.set_protected("volume-1", True)

        assert service.eligible("volume-1") is False

    def test_disabled_policy(self):
        gc, volumes, _, _, service = _build()
        volumes.add("volume-1", "scope-1", status="AVAILABLE")
        policy = service.configure("scope-1", "VOLUME", 3600)

        assert service.eligible("volume-1") is True

        disabled = service.disable(policy.policy_id)

        assert disabled.enabled is False
        assert service.eligible("volume-1") is False

    def test_resource_type_isolation(self):
        gc, volumes, snapshots, replicas, service = _build()
        volumes.add("volume-1", "scope-1", status="AVAILABLE")
        snapshots.add("snapshot-1", "volume-1")
        replicas.add("replica-1", "volume-1")

        service.configure("scope-1", "VOLUME", 3600)

        assert service.eligible("volume-1") is True
        assert service.eligible("snapshot-1") is False
        assert service.eligible("replica-1") is False

        service.configure("scope-1", "SNAPSHOT", 60)

        assert service.eligible("snapshot-1") is True
        assert service.eligible("replica-1") is False

    def test_invalid_retention(self):
        _, _, _, _, service = _build()

        with pytest.raises(Error):
            service.configure("scope-1", "VOLUME", 0)

        with pytest.raises(Error):
            service.configure("scope-1", "VOLUME", -10)
