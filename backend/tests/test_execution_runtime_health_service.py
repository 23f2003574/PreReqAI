import pytest

from backend.session import (
    ExecutionRuntimeHealth,
    ExecutionRuntimeHealthError as Error,
    ExecutionRuntimeHealthService,
)


class _FakeStateRecord:
    def __init__(self, state):
        self.state = state


class _FakeStateService:
    def __init__(self, state_by_runtime=None):
        self._state_by_runtime = dict(state_by_runtime or {})

    def state(self, runtime_id):
        if runtime_id not in self._state_by_runtime:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return _FakeStateRecord(self._state_by_runtime[runtime_id])


class _FakeHeartbeatService:
    def __init__(self, healthy_runtimes=None):
        self._healthy_runtimes = set(healthy_runtimes if healthy_runtimes is not None else {"runtime-1"})
        self._stale_runtimes = ()

    def healthy(self, runtime_id, timeout):
        return runtime_id in self._healthy_runtimes

    def set_stale_runtimes(self, runtime_ids):
        self._stale_runtimes = tuple(runtime_ids)

    def stale(self):
        return self._stale_runtimes


class _FakeTimeoutService:
    def __init__(self, configured_within_limit=None, expired_runtime_ids=()):
        self._configured_within_limit = dict(configured_within_limit or {})
        self._expired_runtime_ids = tuple(expired_runtime_ids)

    def check(self, runtime_id):
        if runtime_id not in self._configured_within_limit:
            raise ValueError(f"no timeout configured for {runtime_id!r}")

        return self._configured_within_limit[runtime_id]

    def expired(self):
        return self._expired_runtime_ids


class _FakeResourceService:
    def __init__(self, leaked_runtime_ids=()):
        self._leaked = [type("Resource", (), {"runtime_id": runtime_id})() for runtime_id in leaked_runtime_ids]

    def leaked(self):
        return tuple(self._leaked)


def _build(
    state_by_runtime=None,
    healthy_heartbeat_runtimes=None,
    stale_runtimes=(),
    configured_within_limit=None,
    expired_runtime_ids=(),
    leaked_runtime_ids=(),
):
    state_service = _FakeStateService(state_by_runtime or {"runtime-1": "RUNNING"})
    heartbeat_service = _FakeHeartbeatService(healthy_heartbeat_runtimes)
    heartbeat_service.set_stale_runtimes(stale_runtimes)
    timeout_service = _FakeTimeoutService(configured_within_limit, expired_runtime_ids)
    resource_service = _FakeResourceService(leaked_runtime_ids)

    service = ExecutionRuntimeHealthService(
        state_service, heartbeat_service, timeout_service, resource_service
    )

    return state_service, heartbeat_service, timeout_service, resource_service, service


class TestExecutionRuntimeHealthService:
    def test_healthy_runtime(self):
        _, _, _, _, service = _build(
            healthy_heartbeat_runtimes={"runtime-1"},
            configured_within_limit={"runtime-1": True},
        )

        health = service.check("runtime-1")

        assert isinstance(health, ExecutionRuntimeHealth)
        assert health.status == "HEALTHY"
        assert health.issues == ()
        assert service.healthy("runtime-1") is True

    def test_stale_heartbeat(self):
        _, _, _, _, service = _build(
            healthy_heartbeat_runtimes=set(),
            configured_within_limit={"runtime-1": True},
        )

        health = service.check("runtime-1")

        assert health.status == "DEGRADED"
        assert "stale heartbeat" in health.issues

    def test_timeout_failure(self):
        _, _, _, _, service = _build(
            healthy_heartbeat_runtimes={"runtime-1"},
            configured_within_limit={"runtime-1": False},
        )

        health = service.check("runtime-1")

        assert health.status == "FAILED"
        assert "timeout exceeded" in health.issues

    def test_resource_leak(self):
        _, _, _, _, service = _build(
            healthy_heartbeat_runtimes={"runtime-1"},
            configured_within_limit={"runtime-1": True},
            leaked_runtime_ids=("runtime-1",),
        )

        health = service.check("runtime-1")

        assert health.status == "FAILED"
        assert "resource leak" in health.issues

    def test_multiple_issues(self):
        _, _, _, _, service = _build(
            healthy_heartbeat_runtimes=set(),
            configured_within_limit={"runtime-1": False},
            leaked_runtime_ids=("runtime-1",),
        )

        health = service.check("runtime-1")

        assert health.status == "FAILED"
        assert set(health.issues) == {"stale heartbeat", "timeout exceeded", "resource leak"}

    def test_deterministic_status(self):
        _, _, _, _, service = _build(
            healthy_heartbeat_runtimes=set(),
            configured_within_limit={"runtime-1": False},
            leaked_runtime_ids=("runtime-1",),
        )

        first = service.check("runtime-1")
        second = service.check("runtime-1")

        assert first.status == second.status == "FAILED"
        assert first.issues == second.issues

    def test_runtime_failed_lifecycle_state_is_failed(self):
        _, _, _, _, service = _build(
            state_by_runtime={"runtime-1": "FAILED"},
            healthy_heartbeat_runtimes={"runtime-1"},
        )

        health = service.check("runtime-1")

        assert health.status == "FAILED"
        assert "runtime failed" in health.issues

    def test_issues_lookup(self):
        _, _, _, _, service = _build(
            healthy_heartbeat_runtimes=set(),
            configured_within_limit={"runtime-1": True},
        )

        assert service.issues("runtime-1") == ("stale heartbeat",)

    def test_unhealthy_sweep(self):
        _, _, _, _, service = _build(
            state_by_runtime={"runtime-1": "RUNNING", "runtime-2": "RUNNING"},
            healthy_heartbeat_runtimes={"runtime-2"},
            stale_runtimes=("runtime-1",),
            configured_within_limit={"runtime-1": True, "runtime-2": True},
        )

        unhealthy = service.unhealthy()

        assert len(unhealthy) == 1
        assert unhealthy[0].runtime_id == "runtime-1"
        assert unhealthy[0].status == "DEGRADED"

    def test_unknown_runtime_is_rejected(self):
        _, _, _, _, service = _build()

        with pytest.raises(Error):
            service.check("does-not-exist")
