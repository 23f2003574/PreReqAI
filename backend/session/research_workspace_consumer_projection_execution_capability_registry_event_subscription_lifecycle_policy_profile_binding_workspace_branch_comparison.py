from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranch,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_comparison_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_difference import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchDifference,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparison:
    """
    Immutable record of a resource-by-resource comparison between two
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace branches.

    The comparison is a value object only. It performs no
    computation. Computing, summarizing, checking for conflicts in,
    and exporting a comparison are the responsibility of a binding
    workspace branch comparison service.

    Attributes:
        comparison_id: The comparison's unique identifier
        source_branch: The branch being compared, treated as the
            reference every difference is expressed relative to
        target_branch: The branch source_branch was compared against
        differences: Every resource-level difference found between
            the two branches, in deterministic order
    """

    comparison_id: str

    source_branch: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranch

    target_branch: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranch

    differences: tuple

    def __post_init__(self):
        if self.comparison_id is None or not self.comparison_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                "Cannot build a branch comparison with an empty or blank comparison ID."
            )

        for label, branch in (
            ("source_branch", self.source_branch),
            ("target_branch", self.target_branch),
        ):
            if not isinstance(
                branch,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranch,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                    f"Cannot build a branch comparison: {label} must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranch."
                )

        if self.source_branch.branch_id == self.target_branch.branch_id:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                "Cannot build a branch comparison: source_branch and target_branch must be different branches."
            )

        if self.differences is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                "Cannot build a branch comparison with None differences."
            )

        for difference in self.differences:
            if not isinstance(
                difference,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchDifference,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                    "Cannot build a branch comparison: every difference must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchDifference."
                )
