import pytest

from backend.session import (
    ExecutionObservationDashboardError as Error,
    ExecutionObservationDashboardService,
    ExecutionObservationError,
    ExecutionObservationErrorService,
    ExecutionObservationMetricService,
    ExecutionObservationTraceService,
)


class _RaisingObservationService:
    """A minimal stand-in exposing metrics()/history(), raising for any session ID it doesn't know about."""

    def __init__(self, known_session_ids):
        self._known_session_ids = set(known_session_ids)

    def metrics(self, session_id):
        return self.history(session_id)

    def history(self, session_id):
        if session_id not in self._known_session_ids:
            raise ValueError(f"unknown session {session_id!r}")

        return []


def _services():
    return (
        ExecutionObservationMetricService(),
        ExecutionObservationTraceService(),
        ExecutionObservationErrorService(),
    )


class TestExecutionObservationDashboardService:
    def test_create_dashboard(self):
        metric_service, trace_service, error_service = _services()
        dashboard_service = ExecutionObservationDashboardService(metric_service, trace_service, error_service)

        dashboard = dashboard_service.create("My Dashboard", ["session-2", "session-1"])

        assert dashboard.name == "My Dashboard"
        assert dashboard.session_ids == ("session-2", "session-1")
        assert dashboard.metrics == {}

    def test_refresh_summary(self):
        metric_service, trace_service, error_service = _services()
        dashboard_service = ExecutionObservationDashboardService(metric_service, trace_service, error_service)
        metric_service.record("session-1", "LATENCY_MS", 100)
        dashboard = dashboard_service.create("Dash", ["session-1"])

        refreshed = dashboard_service.refresh(dashboard.dashboard_id)

        assert refreshed.metrics["metrics"]["LATENCY_MS"] == 100
        assert dashboard_service.summary(dashboard.dashboard_id) == refreshed.metrics

    def test_metric_and_error_aggregation(self):
        metric_service, trace_service, error_service = _services()
        dashboard_service = ExecutionObservationDashboardService(metric_service, trace_service, error_service)

        metric_service.record("session-1", "LATENCY_MS", 100)
        metric_service.record("session-1", "LATENCY_MS", 200)

        trace = trace_service.start("session-1", "stage-1")
        trace_service.finish(trace.trace_id, "SUCCEEDED")

        error_service.record(
            ExecutionObservationError(session_id="session-1", error_type="TIMEOUT", message="timed out")
        )
        error_service.record(
            ExecutionObservationError(session_id="session-1", error_type="TIMEOUT", message="timed out again")
        )
        error_service.record(
            ExecutionObservationError(session_id="session-1", error_type="VALIDATION", message="bad input")
        )

        dashboard = dashboard_service.create("Dash", ["session-1"])
        summary = dashboard_service.refresh(dashboard.dashboard_id).metrics

        assert summary["metrics"]["LATENCY_MS"] == 150
        assert summary["traces"] == {
            "total": 1,
            "active": 0,
            "succeeded": 1,
            "failed": 0,
            "average_duration_seconds": summary["traces"]["average_duration_seconds"],
        }
        assert summary["traces"]["average_duration_seconds"] >= 0
        assert summary["errors"] == {
            "total": 3,
            "by_type": {"TIMEOUT": 2, "VALIDATION": 1},
        }

    def test_session_isolation(self):
        metric_service, trace_service, error_service = _services()
        dashboard_service = ExecutionObservationDashboardService(metric_service, trace_service, error_service)

        metric_service.record("session-1", "LATENCY_MS", 100)
        metric_service.record("session-2", "LATENCY_MS", 999)

        dashboard = dashboard_service.create("Dash", ["session-1"])
        summary = dashboard_service.refresh(dashboard.dashboard_id).metrics

        assert summary["sessions"] == ["session-1"]
        assert summary["metrics"]["LATENCY_MS"] == 100

    def test_delete_dashboard(self):
        metric_service, trace_service, error_service = _services()
        dashboard_service = ExecutionObservationDashboardService(metric_service, trace_service, error_service)
        dashboard = dashboard_service.create("Dash", ["session-1"])

        deleted = dashboard_service.delete(dashboard.dashboard_id)

        assert deleted.dashboard_id == dashboard.dashboard_id

        with pytest.raises(Error):
            dashboard_service.summary(dashboard.dashboard_id)

        with pytest.raises(Error):
            dashboard_service.delete(dashboard.dashboard_id)

    def test_unknown_session_rejection(self):
        fake = _RaisingObservationService(known_session_ids={"session-1"})
        dashboard_service = ExecutionObservationDashboardService(fake, fake, fake)

        with pytest.raises(Error):
            dashboard_service.create("Dash", ["session-1", "session-unknown"])

        dashboard = dashboard_service.create("Dash", ["session-1"])
        assert dashboard.session_ids == ("session-1",)
