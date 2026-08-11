import pytest

from backend.session import (
    ExecutionObservationAlert,
    ExecutionObservationAlertService,
    ExecutionObservationErrorService,
    ExecutionObservationError,
    ExecutionObservationHealthError as Error,
    ExecutionObservationHealthService,
    ExecutionObservationMetricService,
    ExecutionObservationTraceService,
)


class _RaisingObservationService:
    """A minimal stand-in exposing metrics()/history()/active(), raising for unknown session IDs."""

    def __init__(self, known_session_ids):
        self._known_session_ids = set(known_session_ids)

    def metrics(self, session_id):
        return self._check(session_id)

    def history(self, session_id):
        return self._check(session_id)

    def active(self, session_id):
        return self._check(session_id)

    def _check(self, session_id):
        if session_id not in self._known_session_ids:
            raise ValueError(f"unknown session {session_id!r}")

        return []


def _services():
    return (
        ExecutionObservationMetricService(),
        ExecutionObservationTraceService(),
        ExecutionObservationErrorService(),
        ExecutionObservationAlertService(),
    )


class TestExecutionObservationHealthService:
    def test_healthy_session(self):
        metric_service, trace_service, error_service, alert_service = _services()
        health_service = ExecutionObservationHealthService(
            metric_service, trace_service, error_service, alert_service
        )
        metric_service.record("session-1", "LATENCY_MS", 10)

        health = health_service.check("session-1")

        assert health.session_id == "session-1"
        assert health.status == "HEALTHY"
        assert health.reasons == ()

    def test_degraded_session(self):
        metric_service, trace_service, error_service, alert_service = _services()
        health_service = ExecutionObservationHealthService(
            metric_service, trace_service, error_service, alert_service
        )
        error_service.record(
            ExecutionObservationError(session_id="session-1", error_type="TIMEOUT", message="timed out")
        )

        health = health_service.check("session-1")

        assert health.status == "DEGRADED"
        assert len(health.reasons) == 1
        assert "TIMEOUT" in health.reasons[0]

    def test_unhealthy_session(self):
        metric_service, trace_service, error_service, alert_service = _services()
        health_service = ExecutionObservationHealthService(
            metric_service, trace_service, error_service, alert_service
        )
        alert = ExecutionObservationAlert(
            session_id="session-1",
            metric_type="LATENCY_MS",
            threshold=100,
            comparator=">",
            severity="CRITICAL",
        )
        alert_service.register(alert)
        alert_service.evaluate("session-1", "LATENCY_MS", 200)

        # An error is also present, but an active alert takes priority.
        error_service.record(
            ExecutionObservationError(session_id="session-1", error_type="TIMEOUT", message="timed out")
        )

        health = health_service.check("session-1")

        assert health.status == "UNHEALTHY"
        assert any("Alert" in reason and "CRITICAL" in reason for reason in health.reasons)

    def test_reason_aggregation(self):
        metric_service, trace_service, error_service, alert_service = _services()
        health_service = ExecutionObservationHealthService(
            metric_service, trace_service, error_service, alert_service
        )

        alert = ExecutionObservationAlert(
            session_id="session-1",
            metric_type="LATENCY_MS",
            threshold=100,
            comparator=">",
            severity="HIGH",
        )
        alert_service.register(alert)
        alert_service.evaluate("session-1", "LATENCY_MS", 200)

        trace = trace_service.start("session-1", "stage-1")
        trace_service.finish(trace.trace_id, "FAILED")

        error_service.record(
            ExecutionObservationError(session_id="session-1", error_type="TIMEOUT", message="timed out")
        )

        health = health_service.check("session-1")

        assert health.status == "UNHEALTHY"
        assert len(health.reasons) == 3
        # Deterministic order: alerts, then failed traces, then errors.
        assert "Alert" in health.reasons[0]
        assert "Trace" in health.reasons[1]
        assert "Error" in health.reasons[2]

    def test_history(self):
        metric_service, trace_service, error_service, alert_service = _services()
        health_service = ExecutionObservationHealthService(
            metric_service, trace_service, error_service, alert_service
        )

        first = health_service.check("session-1")
        error_service.record(
            ExecutionObservationError(session_id="session-1", error_type="TIMEOUT", message="timed out")
        )
        second = health_service.check("session-1")

        history = health_service.history("session-1")

        assert history == [first, second]
        assert history[0].status == "HEALTHY"
        assert history[1].status == "DEGRADED"

        assert health_service.history("session-2") == []

    def test_unhealthy_and_healthy_listings(self):
        metric_service, trace_service, error_service, alert_service = _services()
        health_service = ExecutionObservationHealthService(
            metric_service, trace_service, error_service, alert_service
        )

        health_service.check("session-healthy")

        alert = ExecutionObservationAlert(
            session_id="session-unhealthy",
            metric_type="LATENCY_MS",
            threshold=100,
            comparator=">",
            severity="HIGH",
        )
        alert_service.register(alert)
        alert_service.evaluate("session-unhealthy", "LATENCY_MS", 200)
        health_service.check("session-unhealthy")

        assert [health.session_id for health in health_service.healthy()] == ["session-healthy"]
        assert [health.session_id for health in health_service.unhealthy()] == ["session-unhealthy"]

    def test_unknown_session(self):
        fake = _RaisingObservationService(known_session_ids={"session-1"})
        health_service = ExecutionObservationHealthService(fake, fake, fake, fake)

        with pytest.raises(Error):
            health_service.check("session-unknown")

        health = health_service.check("session-1")
        assert health.status == "HEALTHY"
