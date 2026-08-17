from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionRuntimeCompletion,
    ExecutionRuntimeCompletionError as Error,
    ExecutionRuntimeCompletionService,
    ExecutionRuntimeFinalizationService,
    ExecutionRuntimeHealthService,
    ExecutionRuntimeHeartbeatService,
    ExecutionRuntimeResourceService,
    ExecutionRuntimeTimeoutService,
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
    """
    Minimal adapter satisfying the union of what every real,
    reused service in this test expects from a runtime state
    service: `.state(runtime_id)` carrying `.state` and
    `.session_id` (ExecutionRuntimeFinalizationService,
    ExecutionRuntimeResourceService, ExecutionRuntimeHealthService),
    `.history(runtime_id)` (ExecutionRuntimeFinalizationService), and
    `.status(runtime_id) -> str` (ExecutionRuntimeHeartbeatService).
    """

    def __init__(self):
        self._state_by_runtime = {}
        self._session_by_runtime = {}
        self._history_by_runtime = {}

    def set_state(self, runtime_id, state, session_id=None):
        self._state_by_runtime[runtime_id] = state

        if session_id is not None:
            self._session_by_runtime[runtime_id] = session_id

    def set_history(self, runtime_id, states_with_times):
        self._history_by_runtime[runtime_id] = [
            _FakeHistoryRecord(state, updated_at) for state, updated_at in states_with_times
        ]

    def state(self, runtime_id):
        if runtime_id not in self._state_by_runtime:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return _FakeStateRecord(
            self._state_by_runtime[runtime_id], self._session_by_runtime.get(runtime_id)
        )

    def status(self, runtime_id):
        return self.state(runtime_id).state

    def history(self, runtime_id):
        if runtime_id not in self._history_by_runtime:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return tuple(self._history_by_runtime[runtime_id])


NOW = datetime.now(timezone.utc)


def _build(heartbeat_timeout_seconds=30):
    state_service = _FakeStateService()
    heartbeat_service = ExecutionRuntimeHeartbeatService(state_service)
    timeout_service = ExecutionRuntimeTimeoutService(state_service)
    resource_service = ExecutionRuntimeResourceService(state_service)
    health_service = ExecutionRuntimeHealthService(
        state_service,
        heartbeat_service,
        timeout_service,
        resource_service,
        heartbeat_timeout_seconds=heartbeat_timeout_seconds,
    )
    finalization_service = ExecutionRuntimeFinalizationService(state_service)
    completion_service = ExecutionRuntimeCompletionService(
        finalization_service, resource_service, health_service
    )

    return (
        state_service,
        heartbeat_service,
        resource_service,
        finalization_service,
        completion_service,
    )


def _bring_up_and_stop(state_service, heartbeat_service, finalization_service, runtime_id, session_id="session-a"):
    started_at = NOW - timedelta(seconds=30)
    finished_at = NOW

    state_service.set_state(runtime_id, "RUNNING", session_id=session_id)
    heartbeat_service.record(runtime_id)

    state_service.set_state(runtime_id, "STOPPED", session_id=session_id)
    state_service.set_history(
        runtime_id,
        [
            ("STARTING", started_at),
            ("RUNNING", started_at + timedelta(seconds=1)),
            ("STOPPING", finished_at - timedelta(seconds=1)),
            ("STOPPED", finished_at),
        ],
    )
    finalization_service.finalize(runtime_id)


class TestExecutionRuntimeCompletionService:
    def test_successful_completion(self):
        state_service, heartbeat_service, _, finalization_service, service = _build()
        _bring_up_and_stop(state_service, heartbeat_service, finalization_service, "runtime-1")

        completion = service.complete("runtime-1")

        assert isinstance(completion, ExecutionRuntimeCompletion)
        assert completion.runtime_id == "runtime-1"
        assert completion.final_status == "SUCCEEDED"
        assert completion.health_status == "HEALTHY"
        assert completion.output_ref == "runtime-output/runtime-1"

    def test_unresolved_health_rejection(self):
        state_service, heartbeat_service, _, finalization_service, service = _build(
            heartbeat_timeout_seconds=-1
        )
        _bring_up_and_stop(state_service, heartbeat_service, finalization_service, "runtime-1")

        with pytest.raises(Error):
            service.complete("runtime-1")

    def test_active_resource_rejection(self):
        state_service, heartbeat_service, resource_service, finalization_service, service = _build()

        state_service.set_state("runtime-1", "RUNNING", session_id="session-a")
        heartbeat_service.record("runtime-1")
        resource_service.allocate("runtime-1", "gpu", 2)

        state_service.set_state("runtime-1", "STOPPED", session_id="session-a")
        started_at = NOW - timedelta(seconds=30)
        state_service.set_history(
            "runtime-1",
            [("STARTING", started_at), ("RUNNING", started_at), ("STOPPING", NOW), ("STOPPED", NOW)],
        )
        finalization_service.finalize("runtime-1")

        with pytest.raises(Error):
            service.complete("runtime-1")

    def test_unfinalized_runtime_rejection(self):
        _, _, _, _, service = _build()

        with pytest.raises(Error):
            service.complete("runtime-1")

    def test_duplicate_completion(self):
        state_service, heartbeat_service, _, finalization_service, service = _build()
        _bring_up_and_stop(state_service, heartbeat_service, finalization_service, "runtime-1")
        service.complete("runtime-1")

        with pytest.raises(Error):
            service.complete("runtime-1")

    def test_result_lookup(self):
        state_service, heartbeat_service, _, finalization_service, service = _build()
        _bring_up_and_stop(state_service, heartbeat_service, finalization_service, "runtime-1")
        completed = service.complete("runtime-1")

        assert service.result("runtime-1").completion_id == completed.completion_id
        assert service.status("runtime-1") == "SUCCEEDED"

    def test_result_lookup_for_incomplete_runtime_is_rejected(self):
        _, _, _, _, service = _build()

        with pytest.raises(Error):
            service.result("does-not-exist")

    def test_session_history(self):
        state_service, heartbeat_service, _, finalization_service, service = _build()
        _bring_up_and_stop(state_service, heartbeat_service, finalization_service, "runtime-1", "session-a")
        _bring_up_and_stop(state_service, heartbeat_service, finalization_service, "runtime-2", "session-a")
        _bring_up_and_stop(state_service, heartbeat_service, finalization_service, "runtime-3", "session-b")

        first = service.complete("runtime-1")
        second = service.complete("runtime-2")
        service.complete("runtime-3")

        history = service.history("session-a")

        assert [c.completion_id for c in history] == [first.completion_id, second.completion_id]

    def test_history_for_unknown_session_is_rejected(self):
        _, _, _, _, service = _build()

        with pytest.raises(Error):
            service.history("does-not-exist")
