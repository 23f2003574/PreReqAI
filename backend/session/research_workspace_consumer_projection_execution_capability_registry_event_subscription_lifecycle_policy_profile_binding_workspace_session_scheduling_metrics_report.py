from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_metrics_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_metric import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetric,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsReport:
    """
    Immutable snapshot of every consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace session scheduling metric retained at the
    moment it was generated, along with a per metric_type summary.

    The report is a value object only. It performs no aggregation.
    Generating reports is the responsibility of a session scheduling
    metrics service.

    Attributes:
        generated_at: When this report was generated
        metrics: Every retained metric included in this report, in
            chronological order by recorded_at
        summary: The mean value of metrics, keyed by metric_type;
            has exactly one entry per distinct metric_type appearing
            in metrics
    """

    generated_at: datetime

    metrics: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetric,
        ...,
    ]

    summary: dict

    def __post_init__(self):
        if self.generated_at is None or not isinstance(self.generated_at, datetime) or self.generated_at.utcoffset() is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError(
                "Cannot build a session scheduling metrics report with a non-timezone-aware generated_at."
            )

        if not isinstance(self.metrics, tuple) or any(
            not isinstance(metric, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetric)
            for metric in self.metrics
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError(
                "Cannot build a session scheduling metrics report with metrics that is not a tuple of "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetric."
            )

        if not isinstance(self.summary, dict) or any(
            not isinstance(metric_type, str)
            or not metric_type.strip()
            or value is None
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            for metric_type, value in self.summary.items()
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError(
                "Cannot build a session scheduling metrics report with a summary that is not a dict of non-blank "
                "metric_type strings to numeric values."
            )

        if set(self.summary.keys()) != {metric.metric_type for metric in self.metrics}:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError(
                "Cannot build a session scheduling metrics report whose summary keys do not match the distinct "
                "metric_type values present in metrics."
            )
