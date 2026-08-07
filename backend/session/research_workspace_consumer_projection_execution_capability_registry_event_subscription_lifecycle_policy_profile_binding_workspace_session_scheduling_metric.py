from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_metrics_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetric:
    """
    Immutable, single measurement taken of a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace session schedule's queue efficiency,
    latency, or other scheduler performance characteristic.

    The metric is a value object only. It performs no aggregation.
    Recording, reporting, aggregating, and purging metrics is the
    responsibility of a session scheduling metrics service.

    Attributes:
        metric_id: The metric's unique identifier
        schedule_id: The identifier of the schedule this measurement
            was taken against
        metric_type: The kind of measurement this is, such as
            "queue_time" or "dispatch_latency"
        value: The measurement itself; must be zero or positive
        recorded_at: When this measurement was taken
    """

    metric_id: str

    schedule_id: str

    metric_type: str

    value: float

    recorded_at: datetime

    def __post_init__(self):
        if self.metric_id is None or not self.metric_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError(
                "Cannot build a session scheduling metric with an empty or blank metric ID."
            )

        if self.schedule_id is None or not self.schedule_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError(
                "Cannot build a session scheduling metric with an empty or blank schedule ID."
            )

        if self.metric_type is None or not self.metric_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError(
                "Cannot build a session scheduling metric with an empty or blank metric_type."
            )

        if (
            self.value is None
            or isinstance(self.value, bool)
            or not isinstance(self.value, (int, float))
            or self.value < 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError(
                "Cannot build a session scheduling metric with a non-negative-numeric value."
            )

        if self.recorded_at is None or not isinstance(self.recorded_at, datetime) or self.recorded_at.utcoffset() is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingMetricsError(
                "Cannot build a session scheduling metric with a non-timezone-aware recorded_at."
            )
