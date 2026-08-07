from dataclasses import (
    dataclass,
)

from datetime import datetime

from typing import Optional

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_schedule_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleResult:
    """
    Immutable report of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace session schedule's next due run after it was advanced
    or cancelled.

    The result is a value object only. It performs no advancing or
    cancellation. Advancing and cancelling a schedule is the
    responsibility of a session scheduler service.

    Attributes:
        schedule_id: The identifier of the schedule this result
            concerns
        next_execution: When the schedule is next due to run, or None
            if it has no further run, such as after it was cancelled
    """

    schedule_id: str

    next_execution: Optional[datetime]

    def __post_init__(self):
        if self.schedule_id is None or not self.schedule_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                "Cannot build a session schedule result with an empty or blank schedule ID."
            )

        if self.next_execution is not None and not isinstance(self.next_execution, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                "Cannot build a session schedule result with a non-datetime next_execution."
            )
