import pytest

from backend.session import (
    ExecutionObservationTraceError as Error,
    ExecutionObservationTraceService,
)


class TestExecutionObservationTraceService:
    def test_start_and_finish_trace(self):
        trace_service = ExecutionObservationTraceService()

        started = trace_service.start("session-1", "stage-1")

        assert started.session_id == "session-1"
        assert started.stage_id == "stage-1"
        assert started.status == "ACTIVE"
        assert started.finished_at is None

        finished = trace_service.finish(started.trace_id, "SUCCEEDED")

        assert finished.trace_id == started.trace_id
        assert finished.status == "SUCCEEDED"
        assert finished.finished_at is not None

    def test_active_lookup(self):
        trace_service = ExecutionObservationTraceService()
        first = trace_service.start("session-1", "stage-1")
        second = trace_service.start("session-1", "stage-2")

        assert trace_service.active("session-1") == [first, second]

        trace_service.finish(first.trace_id, "SUCCEEDED")

        assert trace_service.active("session-1") == [second]

    def test_duration(self):
        trace_service = ExecutionObservationTraceService()
        started = trace_service.start("session-1", "stage-1")

        with pytest.raises(Error):
            trace_service.duration(started.trace_id)

        finished = trace_service.finish(started.trace_id, "SUCCEEDED")
        duration = trace_service.duration(started.trace_id)

        assert duration == (finished.finished_at - finished.started_at).total_seconds()
        assert duration >= 0

    def test_history_ordering(self):
        trace_service = ExecutionObservationTraceService()
        first = trace_service.start("session-1", "stage-1")
        trace_service.finish(first.trace_id, "SUCCEEDED")
        second = trace_service.start("session-1", "stage-2")

        history = trace_service.history("session-1")

        assert [trace.trace_id for trace in history] == [first.trace_id, second.trace_id]

    def test_duplicate_active_trace_rejection(self):
        trace_service = ExecutionObservationTraceService()
        trace_service.start("session-1", "stage-1")

        with pytest.raises(Error):
            trace_service.start("session-1", "stage-1")

        # A different stage in the same session is unaffected.
        trace_service.start("session-1", "stage-2")

    def test_unknown_trace_rejection(self):
        trace_service = ExecutionObservationTraceService()

        with pytest.raises(Error):
            trace_service.finish("unknown-trace", "SUCCEEDED")

        with pytest.raises(Error):
            trace_service.duration("unknown-trace")

    def test_finished_trace_is_immutable(self):
        trace_service = ExecutionObservationTraceService()
        started = trace_service.start("session-1", "stage-1")
        trace_service.finish(started.trace_id, "SUCCEEDED")

        with pytest.raises(Error):
            trace_service.finish(started.trace_id, "FAILED")

        # The now-free stage can start a new trace.
        restarted = trace_service.start("session-1", "stage-1")
        assert restarted.trace_id != started.trace_id
