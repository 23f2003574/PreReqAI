import pytest

from backend.session import (
    ExecutionEventService,
    ExecutionObservabilityEvent,
    ExecutionObservabilityEventError as Error,
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
    return runtime_service, ExecutionEventService(runtime_service)


class TestExecutionEventService:
    def test_record_event(self):
        _, service = _build()

        event = service.record("runtime-1", "STARTED", "INFO", {"pid": 123})

        assert isinstance(event, ExecutionObservabilityEvent)
        assert event.runtime_id == "runtime-1"
        assert event.event_type == "STARTED"
        assert event.severity == "INFO"
        assert event.payload == {"pid": 123}
        assert event.occurred_at is not None

    def test_history_ordering(self):
        _, service = _build()

        first = service.record("runtime-1", "STARTED", "INFO", None)
        second = service.record("runtime-1", "PROGRESS", "DEBUG", None)
        third = service.record("runtime-1", "COMPLETED", "INFO", None)

        history = service.history("runtime-1")

        assert history == (first, second, third)

    def test_event_filtering(self):
        _, service = _build()

        started = service.record("runtime-1", "STARTED", "INFO", None)
        service.record("runtime-1", "PROGRESS", "DEBUG", None)
        started_again = service.record("runtime-1", "STARTED", "INFO", None)

        filtered = service.filter("runtime-1", "STARTED")

        assert filtered == (started, started_again)

    def test_latest_event(self):
        _, service = _build()

        assert service.latest("runtime-1") is None

        service.record("runtime-1", "STARTED", "INFO", None)
        second = service.record("runtime-1", "PROGRESS", "DEBUG", None)

        assert service.latest("runtime-1").event_id == second.event_id

    def test_all_valid_severities_accepted(self):
        _, service = _build()

        for severity in ("DEBUG", "INFO", "WARNING", "ERROR"):
            event = service.record("runtime-1", "STARTED", severity, None)
            assert event.severity == severity

    def test_invalid_severity_rejection(self):
        _, service = _build()

        with pytest.raises(Error):
            service.record("runtime-1", "STARTED", "CRITICAL", None)

    def test_unknown_runtime_rejection(self):
        _, service = _build()

        with pytest.raises(Error):
            service.record("does-not-exist", "STARTED", "INFO", None)

    def test_runtime_isolation(self):
        _, service = _build()

        service.record("runtime-1", "STARTED", "INFO", None)

        assert service.history("runtime-2") == ()
        assert service.filter("runtime-2", "STARTED") == ()
        assert service.latest("runtime-2") is None

    def test_events_are_append_only(self):
        _, service = _build()

        first = service.record("runtime-1", "STARTED", "INFO", None)
        service.record("runtime-1", "COMPLETED", "INFO", None)

        with pytest.raises(Exception):
            first.severity = "ERROR"

        history = service.history("runtime-1")
        assert len(history) == 2
        assert history[0].event_id == first.event_id
        assert history[0].severity == "INFO"

    def test_recording_does_not_mutate_runtime_service(self):
        runtime_service, service = _build()
        service.record("runtime-1", "STARTED", "INFO", None)

        assert runtime_service.status("runtime-1") == "RUNNING"
