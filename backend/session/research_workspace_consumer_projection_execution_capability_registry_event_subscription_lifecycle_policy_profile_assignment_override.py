from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_override_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverride:
    """
    Immutable description of a temporary assignment override mapping a profile
    to a target with a specific priority and active status.

    Attributes:
        override_id: The unique identifier of the override.
        target_id: The identifier of the target the override is applied to.
        profile_id: The identifier of the profile to override with.
        priority: The priority of the override (non-negative integer, higher wins).
        active: True if the override is currently active, False otherwise.
    """

    override_id: str

    target_id: str

    profile_id: str

    priority: int

    active: bool

    def __post_init__(self):
        if self.override_id is None or not self.override_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError(
                "Cannot build an override with an empty or blank override ID."
            )

        if self.target_id is None or not self.target_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError(
                "Cannot build an override with an empty or blank target ID."
            )

        if self.profile_id is None or not self.profile_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError(
                "Cannot build an override with an empty or blank profile ID."
            )

        if self.priority < 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError(
                "Cannot build an override with a negative priority."
            )
