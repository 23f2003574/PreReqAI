import pytest

from backend.session import (
    ExecutionRuntimePause,
    ExecutionRuntimePauseError as Error,
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
    return state_service, ExecutionRuntimePauseService(state_service)


class TestExecutionRuntimePauseService:
    def test_pause_and_resume(self):
        state_service, service = _build()

        paused = service.pause("runtime-1", "operator request")

        assert isinstance(paused, ExecutionRuntimePause)
        assert paused.runtime_id == "runtime-1"
        assert paused.resumed_at is None
        assert state_service.state("runtime-1").state == "PAUSED"
        assert service.status("runtime-1") == "PAUSED"

        resumed = service.resume("runtime-1")

        assert resumed.pause_id == paused.pause_id
        assert resumed.resumed_at is not None
        assert state_service.state("runtime-1").state == "RUNNING"
        assert service.status("runtime-1") == "RUNNING"

    def test_invalid_pause_transition(self):
        _, service = _build(state_by_runtime={"runtime-1": "STARTING"})

        with pytest.raises(Error):
            service.pause("runtime-1", "too early")

    def test_invalid_resume_transition(self):
        _, service = _build(state_by_runtime={"runtime-1": "RUNNING"})

        with pytest.raises(Error):
            service.resume("runtime-1")

    def test_resume_without_active_pause_is_rejected(self):
        _, service = _build(state_by_runtime={"runtime-1": "RUNNING"})
        service.pause("runtime-1", "operator request")
        service.resume("runtime-1")

        with pytest.raises(Error):
            service.resume("runtime-1")

    def test_terminal_protection(self):
        _, service = _build(state_by_runtime={"runtime-1": "FAILED"})

        with pytest.raises(Error):
            service.pause("runtime-1", "attempt pause")

        with pytest.raises(Error):
            service.resume("runtime-1")

    def test_history_ordering(self):
        _, service = _build()
        first = service.pause("runtime-1", "first pause")
        service.resume("runtime-1")
        second = service.pause("runtime-1", "second pause")
        service.resume("runtime-1")

        history = service.history("runtime-1")

        assert [record.pause_id for record in history] == [first.pause_id, second.pause_id]
        assert history[0].paused_at <= history[1].paused_at
        assert all(record.resumed_at is not None for record in history)

    def test_history_for_unknown_runtime_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.history("does-not-exist")

    def test_reason_preservation(self):
        _, service = _build()
        service.pause("runtime-1", "operator requested maintenance")

        history = service.history("runtime-1")

        assert history[0].reason == "operator requested maintenance"

    def test_pausing_unknown_runtime_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.pause("does-not-exist", "reason")
