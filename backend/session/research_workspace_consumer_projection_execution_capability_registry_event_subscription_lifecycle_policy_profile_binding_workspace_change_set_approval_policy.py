from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_review_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy:
    """
    Immutable rule set describing when a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace change set has collected enough
    reviewer approval to be ready for application.

    The policy is a value object only. It performs no evaluation.
    Evaluating a change set's reviews against the policy is the
    responsibility of a binding workspace change set review service.

    Attributes:
        minimum_approvals: The minimum number of distinct reviewers
            whose current review must be approved before a change set
            is ready
        require_unanimous: Whether every reviewer with a current
            review must have approved, rather than merely
            minimum_approvals of them
    """

    minimum_approvals: int

    require_unanimous: bool

    def __post_init__(self):
        if not isinstance(self.minimum_approvals, int) or isinstance(self.minimum_approvals, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                "Cannot build an approval policy: minimum_approvals must be an int."
            )

        if self.minimum_approvals < 1:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                "Cannot build an approval policy with a minimum_approvals below 1."
            )

        if not isinstance(self.require_unanimous, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                "Cannot build an approval policy: require_unanimous must be a bool."
            )
