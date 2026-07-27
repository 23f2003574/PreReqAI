from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_inheritance_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritance:
    """
    Immutable representation of an inherited profile assignment relationship
    linking a target to a parent scope.

    Attributes:
        target_id: The identifier of the target inheriting the assignment.
        parent_target_id: The identifier of the parent scope the assignment is inherited from.
        inherited_profile_id: The identifier of the profile inherited from the parent.
        inheritance_depth: The distance in the hierarchy to the source of the assignment.
    """

    target_id: str

    parent_target_id: str

    inherited_profile_id: str

    inheritance_depth: int

    def __post_init__(self):
        if self.target_id is None or not self.target_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError(
                "Cannot build an inheritance relation with an empty or blank target ID."
            )

        if self.parent_target_id is None or not self.parent_target_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError(
                "Cannot build an inheritance relation with an empty or blank parent target ID."
            )

        if self.inherited_profile_id is None or not self.inherited_profile_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError(
                "Cannot build an inheritance relation with an empty or blank inherited profile ID."
            )

        if self.inheritance_depth <= 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError(
                "Cannot build an inheritance relation with a non-positive inheritance depth."
            )
