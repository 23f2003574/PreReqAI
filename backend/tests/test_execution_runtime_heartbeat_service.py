import pytest

from backend.session import (
    ExecutionRuntimeHeartbeat,
    ExecutionRuntimeHeartbeatError as Error,
    ExecutionRuntimeHeartbeatService,
)


class _FakeStartupService:
    def __init__(self, status_by_runtime=None):
        self._status_by_runtime = dict(status_by_runtime or {})

    def status(self, runtime_id):
        if runtime_id not in self._status_by_runtime:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return self._status_by_runtime[runtime_id]


def _build(status_by_runtime=None, stale_timeout_seconds=30):
    startup_service = _FakeStartupService(
        status_by_runtime or {"runtime-1": "RUNNING", "runtime-2": "RUNNING"}
    )
    return startup_service, ExecutionRuntimeHeartbeatService(
        startup_service, stale_timeout_seconds=stale_timeout_seconds
    )


class TestExecutionRuntimeHeartbeatService:
    def test_record_heartbeat(self):
        _, service = _build()

        heartbeat = service.record("runtime-1")

        assert isinstance(heartbeat, ExecutionRuntimeHeartbeat)
        assert heartbeat.runtime_id == "runtime-1"
        assert heartbeat.status == "OK"
        assert heartbeat.recorded_at is not None

    def test_latest_lookup(self):
        _, service = _build()

        assert service.last("runtime-1") is None

        first = service.record("runtime-1")
        second = service.record("runtime-1")

        latest = service.last("runtime-1")

        assert latest.heartbeat_id == second.heartbeat_id
        assert latest.heartbeat_id != first.heartbeat_id

    def test_healthy_runtime(self):
        _, service = _build()
        service.record("runtime-1")

        assert service.healthy("runtime-1", timeout=30) is True

    def test_stale_runtime(self):
        _, service = _build(stale_timeout_seconds=-1)
        service.record("runtime-1")

        assert service.healthy("runtime-1", timeout=-1) is False
        assert service.stale() == ("runtime-1",)

    def test_runtime_with_no_heartbeat_is_never_healthy(self):
        _, service = _build()

        assert service.healthy("runtime-1", timeout=9999) is False

    def test_stopped_runtime_rejection(self):
        _, service = _build(status_by_runtime={"runtime-1": "FAILED"})

        with pytest.raises(Error):
            service.record("runtime-1")

    def test_unknown_runtime_rejection(self):
        _, service = _build()

        with pytest.raises(Error):
            service.record("does-not-exist")

    def test_multiple_runtime_isolation(self):
        _, service = _build(stale_timeout_seconds=-1)
        service.record("runtime-1")

        assert service.last("runtime-1") is not None
        assert service.last("runtime-2") is None
        assert service.healthy("runtime-2", timeout=9999) is False
        assert service.stale() == ("runtime-1",)

    def test_recording_does_not_mutate_startup_state(self):
        startup_service, service = _build()
        service.record("runtime-1")

        assert startup_service.status("runtime-1") == "RUNNING"
