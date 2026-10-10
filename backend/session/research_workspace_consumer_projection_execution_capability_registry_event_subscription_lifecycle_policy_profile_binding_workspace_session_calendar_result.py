from dataclasses import (
    dataclass,
)

from datetime import datetime

from typing import Optional

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_calendar_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCalendarResult:
    """
    Immutable report of whether a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace session schedule currently satisfies every
    calendar assigned to it.

    The result is a value object only. It performs no eligibility
    checking. Validating and computing the next valid execution
    against calendars is the responsibility of a session scheduling
    calendar service.

    Attributes:
        executable: Whether the schedule currently satisfies every
            calendar assigned to it
        next_valid_time: The next instant at which the schedule would
            satisfy every calendar assigned to it, or None if
            executable is True or no such instant could be found
    """

    executable: bool

    next_valid_time: Optional[datetime]

    def __post_init__(self):
        if self.executable is None or not isinstance(self.executable, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                "Cannot build a session calendar result with a non-boolean executable."
            )

        if self.next_valid_time is not None and not isinstance(self.next_valid_time, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                "Cannot build a session calendar result with a non-datetime next_valid_time."
            )

        if self.executable and self.next_valid_time is not None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                "Cannot build a session calendar result that is executable but still names a next_valid_time."
            )
