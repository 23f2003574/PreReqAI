import pytest

from backend.session import (
    ExecutionTrace,
    ExecutionTraceError as Error,
    ExecutionTraceService,
)


class _FakeRuntimeService:
    def __init__(self, statuses=None):
        self._statuses = dict(statuses or {})

    def status(self, runtime_id):
        if runtime_id not in self._statuses:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return self._statuses[runtime_id]


def _build(statuses=None):
    runtime_service = _FakeRuntimeService(
        statuses or {"runtime-1": "RUNNING", "runtime-2": "RUNNING"}
    )
    return runtime_service, ExecutionTraceService(runtime_service)


class TestExecutionTraceService:
    def test_start_and_finish(self):
        _, service = _build()

        trace = service.start("runtime-1", "ingest_document")

        assert isinstance(trace, ExecutionTrace)
        assert trace.status == "ACTIVE"
        assert trace.finished_at is None
        assert trace.parent_span_id is None

        finished = service.finish(trace.trace_id, "COMPLETED")

        assert finished.trace_id == trace.trace_id
        assert finished.status == "COMPLETED"
        assert finished.finished_at is not None

    def test_nested_trace(self):
        _, service = _build()

        parent = service.start("runtime-1", "ingest_document")
        child = service.start("runtime-1", "parse_pdf", parent_span_id=parent.trace_id)

        assert child.parent_span_id == parent.trace_id
        assert service.children(parent.trace_id) == (child,)

    def test_invalid_parent_rejection(self):
        _, service = _build()

        with pytest.raises(Error):
            service.start("runtime-1", "parse_pdf", parent_span_id="does-not-exist")

    def test_active_lookup(self):
        _, service = _build()

        first = service.start("runtime-1", "ingest_document")
        second = service.start("runtime-1", "parse_pdf")
        service.finish(second.trace_id, "COMPLETED")

        assert service.active("runtime-1") == (first,)

    def test_invalid_state_transition_already_finished(self):
        _, service = _build()

        trace = service.start("runtime-1", "ingest_document")
        service.finish(trace.trace_id, "COMPLETED")

        with pytest.raises(Error):
            service.finish(trace.trace_id, "FAILED")

    def test_invalid_state_transition_unknown_status(self):
        _, service = _build()

        trace = service.start("runtime-1", "ingest_document")

        with pytest.raises(Error):
            service.finish(trace.trace_id, "DONE")

    def test_finish_unknown_trace_rejection(self):
        _, service = _build()

        with pytest.raises(Error):
            service.finish("does-not-exist", "COMPLETED")

    def test_trace_ordering(self):
        _, service = _build()

        first = service.start("runtime-1", "step_one")
        second = service.start("runtime-1", "step_two")
        third = service.start("runtime-1", "step_three")

        assert service.history("runtime-1") == (first, second, third)

    def test_unknown_runtime_rejection(self):
        _, service = _build()

        with pytest.raises(Error):
            service.start("does-not-exist", "ingest_document")

    def test_runtime_isolation(self):
        _, service = _build()

        service.start("runtime-1", "ingest_document")

        assert service.history("runtime-2") == ()
        assert service.active("runtime-2") == ()

    def test_finished_trace_is_immutable(self):
        _, service = _build()

        trace = service.start("runtime-1", "ingest_document")
        finished = service.finish(trace.trace_id, "COMPLETED")

        with pytest.raises(Exception):
            finished.status = "FAILED"

        assert service.history("runtime-1")[0].status == "COMPLETED"
