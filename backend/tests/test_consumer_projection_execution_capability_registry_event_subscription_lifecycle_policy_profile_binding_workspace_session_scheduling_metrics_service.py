from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetric as Metric,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsReport as Report,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsService as MetricsService,
)


def _at(offset_seconds=0):
    return datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)


def _metric(metric_id, schedule_id, metric_type, value, recorded_at=None):
    return Metric(
        metric_id=metric_id,
        schedule_id=schedule_id,
        metric_type=metric_type,
        value=value,
        recorded_at=recorded_at if recorded_at is not None else _at(),
    )


class TestWorkspaceSessionSchedulingMetricsService:
    def test_record_metric(self):
        service = MetricsService()
        metric = _metric("metric-1", "schedule-1", "queue_time", 5.0)

        recorded = service.record(metric)

        assert isinstance(recorded, Metric)
        assert recorded.metric_id == "metric-1"

        with pytest.raises(Error):
            service.record(metric)

    def test_generate_report(self):
        service = MetricsService()
        service.record(_metric("metric-1", "schedule-1", "queue_time", 4.0))
        service.record(_metric("metric-2", "schedule-1", "queue_time", 6.0))
        service.record(_metric("metric-3", "schedule-2", "dispatch_latency", 2.0))

        report = service.report()

        assert isinstance(report, Report)
        assert len(report.metrics) == 3
        assert report.summary == {"queue_time": 5.0, "dispatch_latency": 2.0}
        assert list(report.metrics) == sorted(report.metrics, key=lambda metric: metric.recorded_at)

    def test_aggregate_metrics(self):
        service = MetricsService()
        service.record(_metric("metric-1", "schedule-1", "queue_time", 4.0))
        service.record(_metric("metric-2", "schedule-2", "queue_time", 6.0))

        assert service.aggregate("queue_time") == 5.0

        with pytest.raises(Error):
            service.aggregate("unknown_type")

    def test_history_lookup(self):
        service = MetricsService()
        earlier = _at(-10)
        later = _at(-5)

        # recorded out of chronological order on purpose
        service.record(_metric("metric-1", "schedule-1", "queue_time", 4.0, recorded_at=later))
        service.record(_metric("metric-2", "schedule-1", "queue_time", 6.0, recorded_at=earlier))
        service.record(_metric("metric-3", "schedule-2", "queue_time", 1.0))

        history = service.history("schedule-1")

        assert [metric.metric_id for metric in history] == ["metric-2", "metric-1"]

        with pytest.raises(Error):
            service.history("   ")

    def test_purge_metrics(self):
        service = MetricsService()
        old = _metric("metric-1", "schedule-1", "queue_time", 4.0, recorded_at=_at(-600))
        recent = _metric("metric-2", "schedule-1", "queue_time", 6.0, recorded_at=_at(0))
        service.record(old)
        service.record(recent)

        removed = service.purge(_at(-300))

        assert [metric.metric_id for metric in removed] == ["metric-1"]
        assert service.history("schedule-1") == (recent,)

        with pytest.raises(Error):
            service.purge(datetime.now())

    def test_invalid_metric_rejection(self):
        with pytest.raises(Error):
            Metric(metric_id="   ", schedule_id="schedule-1", metric_type="queue_time", value=1.0, recorded_at=_at())

        with pytest.raises(Error):
            Metric(metric_id="m1", schedule_id="schedule-1", metric_type="queue_time", value=-1.0, recorded_at=_at())

        with pytest.raises(Error):
            Metric(metric_id="m1", schedule_id="schedule-1", metric_type="queue_time", value="fast", recorded_at=_at())

        with pytest.raises(Error):
            Metric(
                metric_id="m1",
                schedule_id="schedule-1",
                metric_type="queue_time",
                value=1.0,
                recorded_at=datetime.now(),
            )

        service = MetricsService()

        with pytest.raises(Error):
            service.record("not-a-metric")

        with pytest.raises(Error):
            service.aggregate("   ")

        with pytest.raises(Error):
            Report(generated_at=_at(), metrics=(), summary={"queue_time": 1.0})
