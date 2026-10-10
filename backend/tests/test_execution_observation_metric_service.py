import pytest

from backend.session import (
    ExecutionObservationMetricError as Error,
    ExecutionObservationMetricService,
)


class TestExecutionObservationMetricService:
    def test_record_metric(self):
        metric_service = ExecutionObservationMetricService()

        recorded = metric_service.record("session-1", "LATENCY_MS", 10)

        assert recorded.session_id == "session-1"
        assert recorded.metric_type == "LATENCY_MS"
        assert recorded.value == 10
        assert metric_service.metrics("session-1") == [recorded]

    def test_aggregate_values(self):
        metric_service = ExecutionObservationMetricService()
        metric_service.record("session-1", "LATENCY_MS", 10)
        metric_service.record("session-1", "LATENCY_MS", 20)
        metric_service.record("session-1", "LATENCY_MS", 30)

        assert metric_service.aggregate("session-1", "LATENCY_MS") == 20

        with pytest.raises(Error):
            metric_service.aggregate("session-1", "UNKNOWN_TYPE")

    def test_session_isolation(self):
        metric_service = ExecutionObservationMetricService()
        metric_service.record("session-1", "LATENCY_MS", 10)
        metric_service.record("session-2", "LATENCY_MS", 1000)

        assert metric_service.metrics("session-1") == [metric_service.metrics("session-1")[0]]
        assert [metric.value for metric in metric_service.metrics("session-1")] == [10]
        assert [metric.value for metric in metric_service.metrics("session-2")] == [1000]
        assert metric_service.aggregate("session-1", "LATENCY_MS") == 10
        assert metric_service.aggregate("session-2", "LATENCY_MS") == 1000

    def test_history_lookup(self):
        metric_service = ExecutionObservationMetricService()
        first = metric_service.record("session-1", "LATENCY_MS", 10)
        second = metric_service.record("session-1", "TOKENS_USED", 5)

        history = metric_service.metrics("session-1")

        assert history == [first, second]

        with pytest.raises(Error):
            metric_service.metrics("")

    def test_invalid_value_rejection(self):
        metric_service = ExecutionObservationMetricService()

        with pytest.raises(Error):
            metric_service.record("session-1", "LATENCY_MS", "not-a-number")

        with pytest.raises(Error):
            metric_service.record("session-1", "LATENCY_MS", True)

        with pytest.raises(Error):
            metric_service.record("session-1", "LATENCY_MS", None)
