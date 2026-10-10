from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionRuntimeTimeout,
    ExecutionRuntimeTimeoutError as Error,
    ExecutionRuntimeTimeoutService,
    ExecutionRuntimePauseError,
    ExecutionRuntimePauseService,
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

    def transition(self, runtime_id, state, reason):
        if runtime_id not in self._state_by_runtime:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        self._state_by_runtime[runtime_id] = state

        return _FakeStateRecord(state)


def _build(state_by_runtime=None):
    state_service = _FakeStateService(state_by_runtime or {"runtime-1": "RUNNING"})
    return state_service, ExecutionRuntimeTimeoutService(state_service)


def _expire(service, runtime_id, seconds_ago=100):
    service._started_at_by_runtime[runtime_id] = datetime.now(timezone.utc) - timedelta(
        seconds=seconds_ago
    )


class TestExecutionRuntimeTimeoutService:
    def test_configure_timeout(self):
        _, service = _build()

        timeout = service.configure("runtime-1", 60)

        assert isinstance(timeout, ExecutionRuntimeTimeout)
        assert timeout.runtime_id == "runtime-1"
        assert timeout.limit_seconds == 60
        assert timeout.status == "ARMED"
        assert timeout.triggered_at is None

    def test_configure_requires_positive_limit(self):
        _, service = _build()

        with pytest.raises(Error):
            service.configure("runtime-1", 0)

        with pytest.raises(Error):
            service.configure("runtime-1", -5)

    def test_configure_requires_active_runtime(self):
        _, service = _build(state_by_runtime={"runtime-1": "FAILED"})

        with pytest.raises(Error):
            service.configure("runtime-1", 60)

    def test_active_runtime_within_limit(self):
        _, service = _build()
        service.configure("runtime-1", 60)

        assert service.check("runtime-1") is True
        assert service.expired() == ()

    def test_timeout_detection(self):
        _, service = _build()
        service.configure("runtime-1", 60)
        _expire(service, "runtime-1")

        assert service.check("runtime-1") is False
        assert service.expired() == ("runtime-1",)

    def test_trigger_transition(self):
        state_service, service = _build()
        service.configure("runtime-1", 60)
        _expire(service, "runtime-1")

        triggered = service.trigger("runtime-1")

        assert triggered.status == "TRIGGERED"
        assert triggered.triggered_at is not None
        assert state_service.state("runtime-1").state == "FAILED"
        assert service.check("runtime-1") is False
        assert service.expired() == ()

    def test_duplicate_trigger_is_idempotent(self):
        _, service = _build()
        service.configure("runtime-1", 60)
        _expire(service, "runtime-1")
        first = service.trigger("runtime-1")

        second = service.trigger("runtime-1")

        assert second.timeout_id == first.timeout_id
        assert second.triggered_at == first.triggered_at

    def test_triggering_unconfigured_runtime_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.trigger("runtime-1")

    def test_resume_after_timeout_rejection(self):
        state_service, timeout_service = _build()
        pause_service = ExecutionRuntimePauseService(state_service)

        timeout_service.configure("runtime-1", 60)
        _expire(timeout_service, "runtime-1")
        timeout_service.trigger("runtime-1")

        with pytest.raises(ExecutionRuntimePauseError):
            pause_service.resume("runtime-1")
