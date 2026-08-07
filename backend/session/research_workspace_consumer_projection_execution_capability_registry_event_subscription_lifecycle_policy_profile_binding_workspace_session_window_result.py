from dataclasses import (
    dataclass,
)

from datetime import datetime

from typing import Optional

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_window_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionWindowResult:
    """
    Immutable report of whether a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace session schedule is currently within an
    approved scheduling window.

    The result is a value object only. It performs no eligibility
    checking. Evaluating and deferring against windows is the
    responsibility of a session scheduling window service.

    Attributes:
        executable: Whether the schedule currently falls within one
            of its approved scheduling windows
        next_window: When the schedule's next approved scheduling
            window opens, or None if executable is True or no future
            window is known
    """

    executable: bool

    next_window: Optional[datetime]

    def __post_init__(self):
        if self.executable is None or not isinstance(self.executable, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError(
                "Cannot build a session window result with a non-boolean executable."
            )

        if self.next_window is not None and not isinstance(self.next_window, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError(
                "Cannot build a session window result with a non-datetime next_window."
            )

        if self.executable and self.next_window is not None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError(
                "Cannot build a session window result that is executable but still names a next_window."
            )
