from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionStorageTier,
    ExecutionStorageTierError as Error,
    ExecutionStorageTieringService,
)


class _FakeVolume:
    def __init__(self, volume_id):
        self.volume_id = volume_id


class _FakeVolumeService:
    def __init__(self):
        self._by_scope = {}

    def add(self, scope_id, volume_id):
        self._by_scope.setdefault(scope_id, []).append(volume_id)

    def for_scope(self, scope_id):
        return tuple(_FakeVolume(volume_id) for volume_id in self._by_scope.get(scope_id, []))


class _FakeMountService:
    def __init__(self):
        self._mounts = {}

    def add_mount(self, resource_id, mount_id="mount-1"):
        self._mounts.setdefault(resource_id, []).append(mount_id)

    def volume_mounts(self, resource_id):
        return tuple(self._mounts.get(resource_id, ()))


class _FakeCheck:
    def __init__(self, status):
        self.status = status


class _FakeIntegrityService:
    def __init__(self):
        self._status = {}

    def set_status(self, resource_id, status):
        self._status[resource_id] = status

    def check(self, resource_id):
        return _FakeCheck(self._status.get(resource_id, "OK"))


class _FakeAccessService:
    def __init__(self):
        self._last_accessed = {}

    def set_last_accessed(self, resource_id, when):
        self._last_accessed[resource_id] = when

    def last_accessed(self, resource_id):
        if resource_id not in self._last_accessed:
            raise ValueError(f"unknown resource {resource_id!r}")

        return self._last_accessed[resource_id]


def _ago(seconds):
    return datetime.now(timezone.utc) - timedelta(seconds=seconds)


def _build(warm_after_seconds=3600, cold_after_seconds=86400):
    volumes = _FakeVolumeService()
    mounts = _FakeMountService()
    integrity = _FakeIntegrityService()
    access = _FakeAccessService()
    service = ExecutionStorageTieringService(
        volumes,
        mounts,
        integrity,
        access,
        warm_after_seconds=warm_after_seconds,
        cold_after_seconds=cold_after_seconds,
    )

    return volumes, mounts, integrity, access, service


class TestExecutionStorageTieringService:
    def test_tier_evaluation(self):
        _, _, _, access, service = _build()
        access.set_last_accessed("volume-1", _ago(10))
        access.set_last_accessed("volume-2", _ago(7200))
        access.set_last_accessed("volume-3", _ago(100000))

        assert service.evaluate("volume-1") == "HOT"
        assert service.evaluate("volume-2") == "WARM"
        assert service.evaluate("volume-3") == "COLD"

    def test_hot_resource_protection(self):
        _, mounts, _, access, service = _build()
        access.set_last_accessed("volume-1", _ago(100000))
        mounts.add_mount("volume-1")

        assert service.evaluate("volume-1") == "HOT"

        with pytest.raises(Error):
            service.transition("volume-1", "COLD")

        transitioned = service.transition("volume-1", "HOT")
        assert isinstance(transitioned, ExecutionStorageTier)
        assert transitioned.tier == "HOT"

    def test_warm_cold_transition(self):
        _, _, _, access, service = _build()
        access.set_last_accessed("volume-1", _ago(7200))

        warm = service.transition("volume-1", "WARM")
        assert warm.tier == "WARM"
        assert service.tier("volume-1") == "WARM"

        access.set_last_accessed("volume-1", _ago(100000))
        cold = service.transition("volume-1", "COLD")
        assert cold.tier == "COLD"
        assert service.tier("volume-1") == "COLD"

    def test_corrupted_resource_rejection(self):
        _, _, integrity, access, service = _build()
        access.set_last_accessed("volume-1", _ago(10))
        integrity.set_status("volume-1", "CORRUPT")

        with pytest.raises(Error):
            service.evaluate("volume-1")

        with pytest.raises(Error):
            service.transition("volume-1", "HOT")

    def test_candidate_lookup(self):
        volumes, _, _, access, service = _build()
        volumes.add("scope-1", "volume-1")
        volumes.add("scope-1", "volume-2")
        access.set_last_accessed("volume-1", _ago(10))
        access.set_last_accessed("volume-2", _ago(7200))
        service.transition("volume-2", "WARM")

        candidates = service.candidates("scope-1")

        assert candidates == ("volume-1",)

    def test_transition_history(self):
        _, _, _, access, service = _build()
        access.set_last_accessed("volume-1", _ago(10))

        first = service.transition("volume-1", "HOT")

        access.set_last_accessed("volume-1", _ago(7200))
        second = service.transition("volume-1", "WARM")

        assert service.history("volume-1") == (first, second)
