from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_metrics_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_metric import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetric,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_metrics_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsReport,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsService:
    """
    Collects consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace session
    scheduling metrics, so queue efficiency, latency, and other
    scheduler performance characteristics can be measured and
    reported on without affecting execution itself.

    The service's responsibility is bookkeeping and reporting only,
    not execution. It does NOT emit metrics on its own; a caller,
    such as the session scheduler, is expected to call record() as
    scheduling events occur.

    Behavior:
    - Metrics are append-only: record() never overwrites an existing
      metric_id, and no method updates a metric once recorded
    - history() and report() always order metrics chronologically, by
      recorded_at
    - aggregate() and a report's summary both report the mean value
      across every retained metric of a given metric_type
    - purge() is the only way retention is bounded: a caller decides,
      each time it calls purge(), how far back to keep metrics

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._metrics = {}
        self._lock = RLock()

    def record(
        self,
        metric: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetric,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetric:
        """
        Record a metric.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError:
                If metric is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetric,
                or its metric ID is already registered
        """

        if not isinstance(metric, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetric):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError(
                "Cannot record an invalid metric: metric must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetric."
            )

        with self._lock:
            if metric.metric_id in self._metrics:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError(
                    f"Metric ID {metric.metric_id!r} is already recorded."
                )

            self._metrics[metric.metric_id] = metric

            return metric

    def report(self) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsReport:
        """
        Generate a report covering every currently retained metric.
        """

        with self._lock:
            metrics = self._chronological(self._metrics.values())

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsReport(
                generated_at=datetime.now(timezone.utc),
                metrics=metrics,
                summary=self._summarize(metrics),
            )

    def history(self, schedule_id: str) -> tuple:
        """
        List every retained metric recorded against a schedule, in
        chronological order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError:
                If schedule_id is None or blank
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            matching = (metric for metric in self._metrics.values() if metric.schedule_id == schedule_id)

            return self._chronological(matching)

    def aggregate(self, metric_type: str) -> float:
        """
        Compute the mean value across every retained metric of a
        given metric_type.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError:
                If metric_type is None or blank, or no metric of that
                type is currently retained
        """

        self._validate_id(metric_type, "metric type")

        with self._lock:
            values = [metric.value for metric in self._metrics.values() if metric.metric_type == metric_type]

            if not values:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError(
                    f"No metric of metric_type {metric_type!r} is currently retained."
                )

            return sum(values) / len(values)

    def purge(self, before_timestamp: datetime) -> tuple:
        """
        Remove every retained metric recorded before a given instant.

        Returns:
            The metrics that were removed, in chronological order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError:
                If before_timestamp is not a timezone-aware datetime
        """

        if (
            before_timestamp is None
            or not isinstance(before_timestamp, datetime)
            or before_timestamp.utcoffset() is None
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError(
                "Cannot purge with a before_timestamp that is not a timezone-aware datetime."
            )

        with self._lock:
            removed = self._chronological(
                metric for metric in self._metrics.values() if metric.recorded_at < before_timestamp
            )

            for metric in removed:
                del self._metrics[metric.metric_id]

            return removed

    def _summarize(self, metrics: tuple) -> dict:
        values_by_type = {}

        for metric in metrics:
            values_by_type.setdefault(metric.metric_type, []).append(metric.value)

        return {metric_type: sum(values) / len(values) for metric_type, values in values_by_type.items()}

    def _chronological(self, metrics) -> tuple:
        return tuple(sorted(metrics, key=lambda metric: metric.recorded_at))

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError(
                f"Cannot operate with an empty or blank {label}."
            )
