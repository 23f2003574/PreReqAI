from dataclasses import (
    dataclass,
)

from datetime import datetime

from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_window_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindow:
    """
    Immutable approved time window during which a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace session schedule is permitted to
    execute.

    The window is a value object only. It performs no eligibility
    checking. Assigning, validating, and deferring against windows is
    the responsibility of a session scheduling window service.

    Attributes:
        window_id: The window's unique identifier
        schedule_id: The identifier of the schedule this window
            applies to
        start_time: When this window opens, as a timezone-aware
            instant
        end_time: When this window closes, as a timezone-aware
            instant, strictly after start_time
        timezone: The IANA time zone key this window is expressed in,
            for evaluation and display purposes
    """

    window_id: str

    schedule_id: str

    start_time: datetime

    end_time: datetime

    timezone: str

    def __post_init__(self):
        if self.window_id is None or not self.window_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError(
                "Cannot build a session scheduling window with an empty or blank window ID."
            )

        if self.schedule_id is None or not self.schedule_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError(
                "Cannot build a session scheduling window with an empty or blank schedule ID."
            )

        if self.start_time is None or not isinstance(self.start_time, datetime) or self.start_time.utcoffset() is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError(
                "Cannot build a session scheduling window with a non-timezone-aware start_time."
            )

        if self.end_time is None or not isinstance(self.end_time, datetime) or self.end_time.utcoffset() is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError(
                "Cannot build a session scheduling window with a non-timezone-aware end_time."
            )

        if self.end_time <= self.start_time:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError(
                "Cannot build a session scheduling window with end_time at or before start_time."
            )

        if self.timezone is None or not self.timezone.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError(
                "Cannot build a session scheduling window with an empty or blank timezone."
            )

        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError(
                f"Cannot build a session scheduling window with unknown timezone {self.timezone!r}."
            ) from error
