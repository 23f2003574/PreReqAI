from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_comparison_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError,
)

_VALID_RESOURCE_TYPES = (
    "binding",
    "template",
    "preset",
    "group",
)

_VALID_CHANGE_TYPES = (
    "addition",
    "update",
    "deletion",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchDifference:
    """
    Immutable record of a single resource-level difference found
    between two consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    branches.

    The difference is a value object only. It performs no
    computation. Computing differences between two branches is the
    responsibility of a binding workspace branch comparison service.

    Attributes:
        resource_type: The kind of member resource the difference
            concerns (one of "binding", "template", "preset", or
            "group")
        resource_id: The identifier of the member resource the
            difference concerns
        change_type: The kind of change the resource represents
            between the two branches (one of "addition", where the
            source branch has or will have the resource and the
            target does not; "deletion", where the target branch has
            the resource and the source does not or will not; or
            "update", where both branches currently share the
            resource but at least one has a pending change queued
            against it)
    """

    resource_type: str

    resource_id: str

    change_type: str

    def __post_init__(self):
        if self.resource_type is None or not self.resource_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                "Cannot build a branch difference with an empty or blank resource type."
            )

        if self.resource_type not in _VALID_RESOURCE_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                f"Invalid branch difference resource type {self.resource_type!r}. Must be one of "
                f"{_VALID_RESOURCE_TYPES!r}."
            )

        if self.resource_id is None or not self.resource_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                "Cannot build a branch difference with an empty or blank resource ID."
            )

        if self.change_type is None or not self.change_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                "Cannot build a branch difference with an empty or blank change type."
            )

        if self.change_type not in _VALID_CHANGE_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                f"Invalid branch difference change type {self.change_type!r}. Must be one of {_VALID_CHANGE_TYPES!r}."
            )
