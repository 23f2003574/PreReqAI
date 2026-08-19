import pytest

from backend.session import (
    ExecutionStorageCostProfile,
    ExecutionStorageCostProfileError as Error,
    ExecutionStorageCostService,
)


class _FakeTieringService:
    def __init__(self):
        self._tier = {}
        self._evaluation = {}
        self.transitions = []

    def set_tier(self, resource_id, tier):
        self._tier[resource_id] = tier

    def set_evaluation(self, resource_id, tier):
        self._evaluation[resource_id] = tier

    def tier(self, resource_id):
        if resource_id not in self._tier:
            raise ValueError(f"unknown resource {resource_id!r}")

        return self._tier[resource_id]

    def evaluate(self, resource_id):
        if resource_id not in self._evaluation:
            raise ValueError(f"unknown resource {resource_id!r}")

        return self._evaluation[resource_id]

    def transition(self, resource_id, tier):
        self.transitions.append((resource_id, tier))
        self._tier[resource_id] = tier


class _FakeRetentionService:
    def __init__(self):
        self._eligible = {}

    def set_eligible(self, resource_id, value):
        self._eligible[resource_id] = value

    def eligible(self, resource_id):
        return self._eligible.get(resource_id, True)


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


def _build():
    tiering = _FakeTieringService()
    retention = _FakeRetentionService()
    integrity = _FakeIntegrityService()
    volumes = _FakeVolumeService()
    service = ExecutionStorageCostService(tiering, retention, integrity, volumes)

    return tiering, retention, integrity, volumes, service


class TestExecutionStorageCostService:
    def test_cost_estimation(self):
        tiering, _, _, _, service = _build()
        tiering.set_tier("volume-1", "HOT")
        tiering.set_tier("volume-2", "COLD")

        assert service.estimate("volume-1") == 1.0
        assert service.estimate("volume-2") == 0.05

    def test_tier_recommendation(self):
        tiering, _, _, _, service = _build()
        tiering.set_tier("volume-1", "HOT")
        tiering.set_evaluation("volume-1", "COLD")

        profile = service.recommend("volume-1")

        assert isinstance(profile, ExecutionStorageCostProfile)
        assert profile.current_tier == "HOT"
        assert profile.recommended_tier == "COLD"
        assert profile.estimated_cost == 1.0

    def test_active_resource_protection(self):
        tiering, retention, _, _, service = _build()
        tiering.set_tier("volume-1", "HOT")
        tiering.set_evaluation("volume-1", "COLD")
        retention.set_eligible("volume-1", False)

        profile = service.recommend("volume-1")
        assert profile.recommended_tier == "HOT"

        with pytest.raises(Error):
            service.apply("volume-1")

    def test_corrupted_resource_protection(self):
        tiering, _, integrity, _, service = _build()
        tiering.set_tier("volume-1", "HOT")
        tiering.set_evaluation("volume-1", "COLD")
        integrity.set_status("volume-1", "CORRUPT")

        profile = service.recommend("volume-1")
        assert profile.recommended_tier == "HOT"

        with pytest.raises(Error):
            service.apply("volume-1")

    def test_candidate_selection(self):
        tiering, _, _, volumes, service = _build()
        volumes.add("scope-1", "volume-1")
        volumes.add("scope-1", "volume-2")
        tiering.set_tier("volume-1", "HOT")
        tiering.set_evaluation("volume-1", "COLD")
        tiering.set_tier("volume-2", "WARM")
        tiering.set_evaluation("volume-2", "WARM")

        candidates = service.candidates("scope-1")

        assert candidates == ("volume-1",)

    def test_invalid_recommendation_rejection(self):
        tiering, _, integrity, _, service = _build()
        tiering.set_tier("volume-1", "HOT")
        tiering.set_evaluation("volume-1", "COLD")

        applied = service.apply("volume-1")

        assert applied.recommended_tier == "COLD"
        assert tiering.transitions == [("volume-1", "COLD")]

        integrity.set_status("volume-1", "CORRUPT")

        with pytest.raises(Error):
            service.apply("volume-1")
