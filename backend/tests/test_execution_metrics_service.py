import pytest

from backend.session import (
    ExecutionMetric,
    ExecutionMetricError as Error,
    ExecutionMetricsService,
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
    return runtime_service, ExecutionMetricsService(runtime_service)


class TestExecutionMetricsService:
    def test_record_metric(self):
        _, service = _build()

        metric = service.record("runtime-1", "latency_ms", 12.5, "ms")

        assert isinstance(metric, ExecutionMetric)
        assert metric.runtime_id == "runtime-1"
        assert metric.name == "latency_ms"
        assert metric.value == 12.5
        assert metric.unit == "ms"
        assert metric.recorded_at is not None

    def test_latest_lookup(self):
        _, service = _build()

        assert service.latest("runtime-1", "latency_ms") is None

        first = service.record("runtime-1", "latency_ms", 10, "ms")
        second = service.record("runtime-1", "latency_ms", 20, "ms")

        latest = service.latest("runtime-1", "latency_ms")

        assert latest.metric_id == second.metric_id
        assert latest.metric_id != first.metric_id

    def test_history_ordering(self):
        _, service = _build()

        first = service.record("runtime-1", "latency_ms", 10, "ms")
        second = service.record("runtime-1", "latency_ms", 20, "ms")
        third = service.record("runtime-1", "latency_ms", 30, "ms")

        history = service.history("runtime-1", "latency_ms")

        assert history == (first, second, third)

    def test_history_isolated_by_name(self):
        _, service = _build()

        service.record("runtime-1", "latency_ms", 10, "ms")
        service.record("runtime-1", "memory_mb", 512, "mb")

        assert len(service.history("runtime-1", "latency_ms")) == 1
        assert len(service.history("runtime-1", "memory_mb")) == 1

    def test_aggregate_mean(self):
        _, service = _build()

        service.record("runtime-1", "latency_ms", 10, "ms")
        service.record("runtime-1", "latency_ms", 20, "ms")
        service.record("runtime-1", "latency_ms", 30, "ms")

        assert service.aggregate("runtime-1", "latency_ms") == 20

    def test_aggregate_without_samples_rejection(self):
        _, service = _build()

        with pytest.raises(Error):
            service.aggregate("runtime-1", "latency_ms")

    def test_invalid_value_rejection(self):
        _, service = _build()

        with pytest.raises(Error):
            service.record("runtime-1", "latency_ms", "not-a-number", "ms")

    def test_boolean_value_rejection(self):
        _, service = _build()

        with pytest.raises(Error):
            service.record("runtime-1", "latency_ms", True, "ms")

    def test_blank_unit_rejection(self):
        _, service = _build()

        with pytest.raises(Error):
            service.record("runtime-1", "latency_ms", 10, "  ")

    def test_missing_unit_rejection(self):
        _, service = _build()

        with pytest.raises(Error):
            service.record("runtime-1", "latency_ms", 10, None)

    def test_unknown_runtime_rejection(self):
        _, service = _build()

        with pytest.raises(Error):
            service.record("does-not-exist", "latency_ms", 10, "ms")

    def test_runtime_isolation(self):
        _, service = _build()

        service.record("runtime-1", "latency_ms", 10, "ms")

        assert service.history("runtime-2", "latency_ms") == ()
        assert service.latest("runtime-2", "latency_ms") is None

    def test_immutable_samples(self):
        _, service = _build()

        metric = service.record("runtime-1", "latency_ms", 10, "ms")

        with pytest.raises(Exception):
            metric.value = 999

        assert service.latest("runtime-1", "latency_ms").value == 10

    def test_recording_does_not_mutate_runtime_service(self):
        runtime_service, service = _build()
        service.record("runtime-1", "latency_ms", 10, "ms")

        assert runtime_service.status("runtime-1") == "RUNNING"
