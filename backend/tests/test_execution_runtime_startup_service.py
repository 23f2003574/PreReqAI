import pytest

from backend.session import (
    ExecutionRuntime,
    ExecutionRuntimeStartupError as Error,
    ExecutionRuntimeStartupService,
)


class _FakeDispatch:
    def __init__(self, status, target=None):
        self.status = status
        self.target = target


class _FakeDispatchService:
    def __init__(self, dispatches_by_id=None):
        self._dispatches_by_id = dict(dispatches_by_id or {})

    def status(self, dispatch_id):
        if dispatch_id not in self._dispatches_by_id:
            raise ValueError(f"unknown dispatch {dispatch_id!r}")

        return self._dispatches_by_id[dispatch_id]


def _build(dispatches_by_id=None):
    dispatch_service = _FakeDispatchService(
        dispatches_by_id
        or {
            "dispatch-1": _FakeDispatch("DISPATCHED", "session-a"),
            "dispatch-2": _FakeDispatch("DISPATCHED", "session-b"),
        }
    )
    return dispatch_service, ExecutionRuntimeStartupService(dispatch_service)


class TestExecutionRuntimeStartupService:
    def test_successful_startup(self):
        _, service = _build()

        runtime = service.start("dispatch-1")

        assert isinstance(runtime, ExecutionRuntime)
        assert runtime.dispatch_id == "dispatch-1"
        assert runtime.session_id == "session-a"
        assert runtime.status == "RUNNING"
        assert runtime.started_at is not None

    def test_invalid_dispatch_is_rejected(self):
        _, service = _build(
            dispatches_by_id={"dispatch-1": _FakeDispatch("CANCELLED", "session-a")}
        )

        with pytest.raises(Error):
            service.start("dispatch-1")

    def test_unknown_dispatch_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.start("does-not-exist")

    def test_duplicate_runtime_is_rejected(self):
        dispatch_service, service = _build(
            dispatches_by_id={
                "dispatch-1": _FakeDispatch("DISPATCHED", "session-a"),
                "dispatch-2": _FakeDispatch("DISPATCHED", "session-a"),
            }
        )
        service.start("dispatch-1")

        with pytest.raises(Error):
            service.start("dispatch-2")

    def test_startup_failure(self):
        _, service = _build()
        runtime = service.start("dispatch-1")

        failed = service.fail(runtime.runtime_id, "boot timeout")

        assert failed.status == "FAILED"

    def test_startup_failure_is_terminal(self):
        _, service = _build()
        runtime = service.start("dispatch-1")
        service.fail(runtime.runtime_id, "boot timeout")

        second = service.fail(runtime.runtime_id, "boot timeout again")

        assert second.status == "FAILED"

    def test_failed_session_can_start_a_new_runtime(self):
        dispatch_service, service = _build(
            dispatches_by_id={
                "dispatch-1": _FakeDispatch("DISPATCHED", "session-a"),
                "dispatch-2": _FakeDispatch("DISPATCHED", "session-a"),
            }
        )
        runtime = service.start("dispatch-1")
        service.fail(runtime.runtime_id, "boot timeout")

        restarted = service.start("dispatch-2")

        assert restarted.status == "RUNNING"

    def test_active_lookup(self):
        _, service = _build()
        runtime = service.start("dispatch-1")

        active = service.active("session-a")

        assert len(active) == 1
        assert active[0].runtime_id == runtime.runtime_id

        service.fail(runtime.runtime_id, "boot timeout")

        assert service.active("session-a") == ()

    def test_status_transition(self):
        _, service = _build()
        runtime = service.start("dispatch-1")

        assert service.status(runtime.runtime_id) == "RUNNING"

        service.fail(runtime.runtime_id, "boot timeout")

        assert service.status(runtime.runtime_id) == "FAILED"

    def test_status_lookup_for_unknown_runtime_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.status("does-not-exist")

    def test_failing_unknown_runtime_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.fail("does-not-exist", "reason")
