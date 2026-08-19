import pytest

from backend.session import (
    ExecutionStorageDecision,
    ExecutionStorageDecisionError as Error,
    ExecutionStorageOrchestrationService,
)


class _FakeQuotaService:
    def __init__(self):
        self._capacity = {}
        self.allocations = []
        self.releases = []

    def set_capacity(self, scope_id, allowed):
        self._capacity[scope_id] = allowed

    def can_allocate(self, scope_id, size):
        return self._capacity.get(scope_id, True)

    def allocate(self, scope_id, size):
        self.allocations.append((scope_id, size))

    def release(self, scope_id, size):
        self.releases.append((scope_id, size))


class _FakeVolume:
    def __init__(self, volume_id, scope_id, size):
        self.volume_id = volume_id
        self.scope_id = scope_id
        self.size = size


class _FakeVolumeService:
    def __init__(self):
        self._counter = 0
        self.detached = []
        self.deleted = []

    def create(self, scope_id, size):
        self._counter += 1

        return _FakeVolume(f"volume-{self._counter}", scope_id, size)

    def detach(self, volume_id, runtime_id):
        self.detached.append((volume_id, runtime_id))

    def delete(self, volume_id):
        self.deleted.append(volume_id)


class _FakeMount:
    def __init__(self, mount_id):
        self.mount_id = mount_id


class _FakeMountService:
    def __init__(self):
        self._mounted_paths = {}
        self._mounts_by_volume = {}
        self._counter = 0
        self.unmounted = []

    def mount(self, volume_id, runtime_id, path, mode):
        key = (runtime_id, path)

        if key in self._mounted_paths:
            raise ValueError(f"duplicate path {path!r} for runtime {runtime_id!r}")

        self._counter += 1
        mount_id = f"mount-{self._counter}"
        self._mounted_paths[key] = mount_id
        self._mounts_by_volume.setdefault(volume_id, []).append(_FakeMount(mount_id))

        return _FakeMount(mount_id)

    def unmount(self, mount_id):
        self.unmounted.append(mount_id)

    def volume_mounts(self, volume_id):
        return tuple(self._mounts_by_volume.get(volume_id, ()))


class _FakeCheck:
    def __init__(self, status):
        self.status = status


class _FakeIntegrityService:
    def __init__(self):
        self._status = {}

    def set_status(self, volume_id, status):
        self._status[volume_id] = status

    def check(self, volume_id):
        return _FakeCheck(self._status.get(volume_id, "OK"))


class _FakeRetentionService:
    def eligible(self, resource_id):
        return True


class _FakeTieringService:
    def evaluate(self, resource_id):
        return "HOT"


class _FakeFailoverResult:
    def __init__(self, selected_target):
        self.selected_target = selected_target


class _FakeFailoverService:
    def __init__(self):
        self._selected = {}

    def set_selected(self, volume_id, target):
        self._selected[volume_id] = target

    def select(self, volume_id):
        if volume_id not in self._selected:
            raise ValueError(f"unknown volume {volume_id!r}")

        return self._selected[volume_id]

    def execute(self, volume_id):
        if volume_id not in self._selected:
            raise ValueError(f"unknown volume {volume_id!r}")

        return _FakeFailoverResult(self._selected[volume_id])


def _build():
    quota = _FakeQuotaService()
    volumes = _FakeVolumeService()
    mounts = _FakeMountService()
    integrity = _FakeIntegrityService()
    retention = _FakeRetentionService()
    tiering = _FakeTieringService()
    failover = _FakeFailoverService()
    service = ExecutionStorageOrchestrationService(
        quota, volumes, mounts, integrity, retention, tiering, failover
    )

    return quota, volumes, mounts, integrity, retention, tiering, failover, service


class TestExecutionStorageOrchestrationService:
    def test_successful_provisioning(self):
        _, _, _, _, _, _, _, service = _build()

        decision = service.provision("runtime-1", 100)

        assert isinstance(decision, ExecutionStorageDecision)
        assert decision.allowed is True
        assert decision.runtime_id == "runtime-1"
        assert decision.volume_id
        assert service.decision(decision.volume_id) == decision

    def test_quota_rejection(self):
        quota, _, _, _, _, _, _, service = _build()
        quota.set_capacity("runtime-1", False)

        with pytest.raises(Error):
            service.provision("runtime-1", 100)

    def test_mount_validation(self):
        _, _, _, _, _, _, _, service = _build()
        decision = service.provision("runtime-1", 100)

        mounted = service.mount("runtime-1", decision.volume_id)
        assert mounted.allowed is True

        rejected = service.mount("runtime-1", decision.volume_id)
        assert rejected.allowed is False

    def test_integrity_failure(self):
        _, _, _, integrity, _, _, _, service = _build()
        decision = service.provision("runtime-1", 100)
        integrity.set_status(decision.volume_id, "CORRUPT")

        evaluated = service.evaluate(decision.volume_id)

        assert evaluated.allowed is False
        assert "integrity" in evaluated.reason

    def test_replica_failover(self):
        _, _, _, _, _, _, failover, service = _build()
        decision = service.provision("runtime-1", 100)
        failover.set_selected(decision.volume_id, "target-b")

        result = service.failover(decision.volume_id)
        assert result.allowed is True
        assert result.target == "target-b"

        failover.set_selected(decision.volume_id, None)
        unavailable = service.failover(decision.volume_id)
        assert unavailable.allowed is False

    def test_release_cleanup(self):
        quota, volumes, mounts, _, _, _, _, service = _build()
        decision = service.provision("runtime-1", 100)
        service.mount("runtime-1", decision.volume_id)

        released = service.release(decision.volume_id)

        assert released.allowed is True
        assert volumes.deleted == [decision.volume_id]
        assert quota.releases == [("runtime-1", 100)]
        assert len(mounts.unmounted) == 1

    def test_deterministic_decision(self):
        _, _, _, _, _, _, failover, service = _build()
        decision = service.provision("runtime-1", 100)
        failover.set_selected(decision.volume_id, "target-a")

        first = service.evaluate(decision.volume_id)
        second = service.evaluate(decision.volume_id)

        assert first.allowed == second.allowed
        assert first.target == second.target
        assert first.reason == second.reason
