from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_template_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateAssignment:
    """
    Immutable record of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace branch template currently assigned to a branch.

    The assignment is a value object only. It performs no assigning
    or unassigning. Those are the responsibility of a binding
    workspace branch template service.

    Attributes:
        branch_id: The identifier of the branch the template is
            assigned to
        template_id: The identifier of the assigned template
        assigned_at: When the template was assigned
    """

    branch_id: str

    template_id: str

    assigned_at: datetime

    def __post_init__(self):
        if self.branch_id is None or not self.branch_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                "Cannot build a branch template assignment with an empty or blank branch ID."
            )

        if self.template_id is None or not self.template_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                "Cannot build a branch template assignment with an empty or blank template ID."
            )

        if self.assigned_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                "Cannot build a branch template assignment with a None assigned_at."
            )
