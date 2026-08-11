import pytest

from backend.session import (
    ExecutionObservationAlertError as Error,
    ExecutionObservationAlert,
    ExecutionObservationAlertService,
)


def _alert(
    session_id="session-1",
    metric_type="LATENCY_MS",
    threshold=100,
    comparator=">",
    severity="HIGH",
    enabled=True,
    alert_id=None,
):
    kwargs = dict(
        session_id=session_id,
        metric_type=metric_type,
        threshold=threshold,
        comparator=comparator,
        severity=severity,
        enabled=enabled,
    )

    if alert_id is not None:
        kwargs["alert_id"] = alert_id

    return ExecutionObservationAlert(**kwargs)


class TestExecutionObservationAlertService:
    def test_register_alert(self):
        alert_service = ExecutionObservationAlertService()
        alert = _alert()

        registered = alert_service.register(alert)

        assert registered == alert
        assert registered.triggered is False

    def test_threshold_trigger(self):
        alert_service = ExecutionObservationAlertService()
        alert = _alert(threshold=100, comparator=">")
        alert_service.register(alert)

        triggered = alert_service.evaluate("session-1", "LATENCY_MS", 150)

        assert [triggered_alert.alert_id for triggered_alert in triggered] == [alert.alert_id]
        assert [active_alert.alert_id for active_alert in alert_service.active("session-1")] == [alert.alert_id]

    def test_non_trigger(self):
        alert_service = ExecutionObservationAlertService()
        alert = _alert(threshold=100, comparator=">")
        alert_service.register(alert)

        triggered = alert_service.evaluate("session-1", "LATENCY_MS", 50)

        assert triggered == []
        assert alert_service.active("session-1") == []

    def test_disable_and_resolve(self):
        alert_service = ExecutionObservationAlertService()
        disabled_alert = _alert(alert_id="alert-disabled", threshold=100, comparator=">", enabled=False)
        alert_service.register(disabled_alert)

        # A disabled alert never triggers, even when its threshold is crossed.
        assert alert_service.evaluate("session-1", "LATENCY_MS", 150) == []
        assert alert_service.active("session-1") == []

        enabled_alert = _alert(alert_id="alert-enabled", threshold=100, comparator=">")
        alert_service.register(enabled_alert)
        alert_service.evaluate("session-1", "LATENCY_MS", 150)

        assert [alert.alert_id for alert in alert_service.active("session-1")] == ["alert-enabled"]

        resolved = alert_service.resolve("alert-enabled")

        assert resolved.triggered is False
        assert alert_service.active("session-1") == []

        # A resolved alert may trigger again.
        alert_service.evaluate("session-1", "LATENCY_MS", 150)
        assert [alert.alert_id for alert in alert_service.active("session-1")] == ["alert-enabled"]

        with pytest.raises(Error):
            alert_service.resolve("unknown-alert")

    def test_multiple_alerts(self):
        alert_service = ExecutionObservationAlertService()
        high_latency = _alert(alert_id="alert-high", metric_type="LATENCY_MS", threshold=100, comparator=">")
        low_throughput = _alert(
            alert_id="alert-low", metric_type="THROUGHPUT", threshold=10, comparator="<", severity="LOW"
        )
        other_session = _alert(alert_id="alert-other", session_id="session-2", threshold=100, comparator=">")
        alert_service.register(high_latency)
        alert_service.register(low_throughput)
        alert_service.register(other_session)

        alert_service.evaluate("session-1", "LATENCY_MS", 150)
        alert_service.evaluate("session-1", "THROUGHPUT", 5)

        active_ids = sorted(alert.alert_id for alert in alert_service.active("session-1"))

        assert active_ids == ["alert-high", "alert-low"]
        assert alert_service.active("session-2") == []

    def test_invalid_threshold(self):
        with pytest.raises(Error):
            _alert(threshold="not-a-number")

        with pytest.raises(Error):
            _alert(threshold=True)

        with pytest.raises(Error):
            _alert(comparator="==")

    def test_duplicate_alert_rejection(self):
        alert_service = ExecutionObservationAlertService()
        alert = _alert(alert_id="alert-1")
        alert_service.register(alert)

        with pytest.raises(Error):
            alert_service.register(_alert(alert_id="alert-1"))

    def test_evaluate_rejects_non_numeric_value(self):
        alert_service = ExecutionObservationAlertService()
        alert_service.register(_alert())

        with pytest.raises(Error):
            alert_service.evaluate("session-1", "LATENCY_MS", "not-a-number")
