import pytest

from backend.session import (
    ExecutionRuntimeState,
    ExecutionRuntimeStateError as Error,
    ExecutionRuntimeStateService,
)


def _build():
    return ExecutionRuntimeStateService()


class TestExecutionRuntimeStateService:
    def test_valid_transitions(self):
        service = _build()

        starting = service.transition("runtime-1", "STARTING", "booting")
        running = service.transition("runtime-1", "RUNNING", "boot complete")
        paused = service.transition("runtime-1", "PAUSED", "operator paused")
        resumed = service.transition("runtime-1", "RUNNING", "operator resumed")
        stopping = service.transition("runtime-1", "STOPPING", "shutdown requested")
        stopped = service.transition("runtime-1", "STOPPED", "shutdown complete")

        assert [r.state for r in (starting, running, paused, resumed, stopping, stopped)] == [
            "STARTING",
            "RUNNING",
            "PAUSED",
            "RUNNING",
            "STOPPING",
            "STOPPED",
        ]

    def test_invalid_transition(self):
        service = _build()
        service.transition("runtime-1", "STARTING", "booting")

        with pytest.raises(Error):
            service.transition("runtime-1", "STOPPED", "skip ahead")

    def test_first_transition_must_be_starting(self):
        service = _build()

        with pytest.raises(Error):
            service.transition("runtime-1", "RUNNING", "skip boot")

    def test_terminal_protection(self):
        service = _build()
        service.transition("runtime-1", "STARTING", "booting")
        service.transition("runtime-1", "FAILED", "boot crashed")

        assert service.can_transition("runtime-1", "RUNNING") is False

        with pytest.raises(Error):
            service.transition("runtime-1", "RUNNING", "retry")

    def test_history_ordering(self):
        service = _build()
        service.transition("runtime-1", "STARTING", "booting")
        service.transition("runtime-1", "RUNNING", "boot complete")
        service.transition("runtime-1", "STOPPING", "shutdown requested")

        history = service.history("runtime-1")

        assert [record.state for record in history] == ["STARTING", "RUNNING", "STOPPING"]
        assert history[0].updated_at <= history[1].updated_at <= history[2].updated_at

    def test_state_lookup(self):
        service = _build()
        service.transition("runtime-1", "STARTING", "booting")
        service.transition("runtime-1", "RUNNING", "boot complete")

        current = service.state("runtime-1")

        assert isinstance(current, ExecutionRuntimeState)
        assert current.state == "RUNNING"

    def test_state_lookup_for_unknown_runtime_is_rejected(self):
        service = _build()

        with pytest.raises(Error):
            service.state("does-not-exist")

    def test_reason_preservation(self):
        service = _build()
        service.transition("runtime-1", "STARTING", "cold start requested")

        assert service.state("runtime-1").reason == "cold start requested"

        service.transition("runtime-1", "RUNNING", "health checks passed")

        history = service.history("runtime-1")

        assert history[0].reason == "cold start requested"
        assert history[1].reason == "health checks passed"

    def test_can_transition_reports_valid_moves(self):
        service = _build()
        service.transition("runtime-1", "STARTING", "booting")

        assert service.can_transition("runtime-1", "RUNNING") is True
        assert service.can_transition("runtime-1", "STOPPED") is False
