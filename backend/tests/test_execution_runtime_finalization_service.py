from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionRuntimeFinalizationError as Error,
    ExecutionRuntimeFinalizationService,
    ExecutionRuntimeResult,
)


class _FakeHistoryRecord:
    def __init__(self, state, updated_at):
        self.state = state
        self.updated_at = updated_at


class _FakeStateRecord:
    def __init__(self, state, session_id):
        self.state = state
        self.session_id = session_id


class _FakeStateService:
    def __init__(self):
        self._state_by_runtime = {}
        self._session_by_runtime = {}
        self._history_by_runtime = {}

    def seed(self, runtime_id, session_id, states_with_times):
        self._session_by_runtime[runtime_id] = session_id
        self._history_by_runtime[runtime_id] = [
            _FakeHistoryRecord(state, updated_at) for state, updated_at in states_with_times
        ]
        self._state_by_runtime[runtime_id] = states_with_times[-1][0]

    def state(self, runtime_id):
        if runtime_id not in self._state_by_runtime:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return _FakeStateRecord(
            self._state_by_runtime[runtime_id], self._session_by_runtime[runtime_id]
        )

    def history(self, runtime_id):
        if runtime_id not in self._history_by_runtime:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return tuple(self._history_by_runtime[runtime_id])


NOW = datetime.now(timezone.utc)


def _seed_stopped(state_service, runtime_id, session_id="session-a", started_at=None, finished_at=None):
    started_at = started_at or (NOW - timedelta(seconds=30))
    finished_at = finished_at or NOW
    state_service.seed(
        runtime_id,
        session_id,
        [
            ("STARTING", started_at),
            ("RUNNING", started_at + timedelta(seconds=1)),
            ("STOPPING", finished_at - timedelta(seconds=1)),
            ("STOPPED", finished_at),
        ],
    )


def _build():
    state_service = _FakeStateService()
    return state_service, ExecutionRuntimeFinalizationService(state_service)


class TestExecutionRuntimeFinalizationService:
    def test_successful_finalization(self):
        state_service, service = _build()
        _seed_stopped(state_service, "runtime-1")

        result = service.finalize("runtime-1")

        assert isinstance(result, ExecutionRuntimeResult)
        assert result.runtime_id == "runtime-1"
        assert result.status == "COMPLETED"

    def test_output_capture(self):
        state_service, service = _build()
        _seed_stopped(state_service, "runtime-1")

        result = service.finalize("runtime-1")

        assert result.output_ref == "runtime-output/runtime-1"

    def test_timestamp_preservation(self):
        state_service, service = _build()
        started_at = NOW - timedelta(seconds=45)
        finished_at = NOW
        _seed_stopped(state_service, "runtime-1", started_at=started_at, finished_at=finished_at)

        result = service.finalize("runtime-1")

        assert result.started_at == started_at
        assert result.finished_at == finished_at

    def test_duplicate_rejection(self):
        state_service, service = _build()
        _seed_stopped(state_service, "runtime-1")
        service.finalize("runtime-1")

        with pytest.raises(Error):
            service.finalize("runtime-1")

    def test_non_stopped_runtime_rejection(self):
        state_service, service = _build()
        state_service.seed("runtime-1", "session-a", [("STARTING", NOW), ("RUNNING", NOW)])

        with pytest.raises(Error):
            service.finalize("runtime-1")

    def test_session_history(self):
        state_service, service = _build()
        _seed_stopped(state_service, "runtime-1", session_id="session-a")
        _seed_stopped(state_service, "runtime-2", session_id="session-a")
        _seed_stopped(state_service, "runtime-3", session_id="session-b")

        first = service.finalize("runtime-1")
        second = service.finalize("runtime-2")
        service.finalize("runtime-3")

        history = service.history("session-a")

        assert [r.result_id for r in history] == [first.result_id, second.result_id]

    def test_result_lookup(self):
        state_service, service = _build()
        _seed_stopped(state_service, "runtime-1")
        finalized = service.finalize("runtime-1")

        assert service.result("runtime-1").result_id == finalized.result_id

    def test_result_lookup_for_unfinalized_runtime_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.result("does-not-exist")

    def test_history_for_unknown_session_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.history("does-not-exist")

    def test_finalizing_unknown_runtime_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.finalize("does-not-exist")
