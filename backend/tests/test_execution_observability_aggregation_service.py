from backend.session import (
    ExecutionEventService,
    ExecutionMetricsService,
    ExecutionObservabilityAggregationService,
    ExecutionObservabilitySummary,
)


class _FakeRuntimeService:
    def __init__(self, statuses=None):
        self._statuses = dict(statuses or {"runtime-1": "RUNNING", "runtime-2": "RUNNING"})

    def status(self, runtime_id):
        if runtime_id not in self._statuses:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return self._statuses[runtime_id]


def _build():
    runtime_service = _FakeRuntimeService()
    metrics_service = ExecutionMetricsService(runtime_service)
    event_service = ExecutionEventService(runtime_service)
    aggregation_service = ExecutionObservabilityAggregationService(metrics_service, event_service)

    return metrics_service, event_service, aggregation_service


class TestExecutionObservabilityAggregationService:
    def test_metric_aggregation(self):
        metrics_service, _, aggregation_service = _build()

        metrics_service.record("runtime-1", "latency_ms", 10, "ms")
        metrics_service.record("runtime-1", "latency_ms", 20, "ms")
        metrics_service.record("runtime-1", "memory_mb", 512, "mb")

        summary = aggregation_service.metrics("runtime-1")

        assert summary["latency_ms"] == {"mean": 15, "unit": "ms", "count": 2}
        assert summary["memory_mb"] == {"mean": 512, "unit": "mb", "count": 1}

    def test_event_counts(self):
        _, event_service, aggregation_service = _build()

        event_service.record("runtime-1", "STARTED", "INFO", None)
        event_service.record("runtime-1", "STARTED", "INFO", None)
        event_service.record("runtime-1", "PROGRESS", "DEBUG", None)

        counts = aggregation_service.events("runtime-1")

        assert counts["by_type"] == {"STARTED": 2, "PROGRESS": 1}
        assert counts["by_severity"] == {"INFO": 2, "DEBUG": 1}

    def test_error_counts(self):
        _, event_service, aggregation_service = _build()

        event_service.record("runtime-1", "STARTED", "INFO", None)
        event_service.record("runtime-1", "TASK_FAILED", "ERROR", None)
        event_service.record("runtime-1", "RETRY", "ERROR", None)

        assert aggregation_service.errors("runtime-1") == 2

    def test_empty_runtime(self):
        _, _, aggregation_service = _build()

        summary = aggregation_service.generate("runtime-2")

        assert isinstance(summary, ExecutionObservabilitySummary)
        assert summary.metrics == {}
        assert summary.event_counts == {"by_type": {}, "by_severity": {}}
        assert summary.error_count == 0

    def test_summary_comparison(self):
        metrics_service, event_service, aggregation_service = _build()

        metrics_service.record("runtime-1", "latency_ms", 10, "ms")
        event_service.record("runtime-1", "STARTED", "INFO", None)
        event_service.record("runtime-1", "TASK_FAILED", "ERROR", None)
        summary_a = aggregation_service.generate("runtime-1")

        metrics_service.record("runtime-2", "latency_ms", 30, "ms")
        event_service.record("runtime-2", "STARTED", "INFO", None)
        summary_b = aggregation_service.generate("runtime-2")

        diff = aggregation_service.compare(summary_a, summary_b)

        assert diff["runtime_a"] == "runtime-1"
        assert diff["runtime_b"] == "runtime-2"
        assert diff["metrics"]["latency_ms"] == {"a": 10, "b": 30, "unit": "ms", "delta": 20}
        assert diff["event_counts"]["by_type"]["STARTED"] == {"a": 1, "b": 1, "delta": 0}
        assert diff["event_counts"]["by_severity"]["ERROR"] == {"a": 1, "b": 0, "delta": -1}
        assert diff["error_count"] == {"a": 1, "b": 0, "delta": -1}

    def test_deterministic_output(self):
        metrics_service, event_service, aggregation_service = _build()

        metrics_service.record("runtime-1", "latency_ms", 10, "ms")
        metrics_service.record("runtime-1", "latency_ms", 20, "ms")
        event_service.record("runtime-1", "STARTED", "INFO", None)
        event_service.record("runtime-1", "TASK_FAILED", "ERROR", None)

        first = aggregation_service.metrics("runtime-1")
        second = aggregation_service.metrics("runtime-1")
        assert first == second

        first_events = aggregation_service.events("runtime-1")
        second_events = aggregation_service.events("runtime-1")
        assert first_events == second_events

        assert aggregation_service.errors("runtime-1") == aggregation_service.errors("runtime-1")

    def test_aggregation_does_not_mutate_source_records(self):
        metrics_service, event_service, aggregation_service = _build()

        metrics_service.record("runtime-1", "latency_ms", 10, "ms")
        event_service.record("runtime-1", "STARTED", "INFO", None)

        aggregation_service.generate("runtime-1")

        assert len(metrics_service.history("runtime-1", "latency_ms")) == 1
        assert len(event_service.history("runtime-1")) == 1
