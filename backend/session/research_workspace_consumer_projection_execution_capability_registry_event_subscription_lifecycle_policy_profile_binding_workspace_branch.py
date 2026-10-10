from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranch:
    """
    Immutable record of a lightweight, independent feature stream
    branching off a consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace.

    The branch is a value object only. It performs no creation,
    checkout, renaming, or closing. Those are the responsibility of a
    binding workspace branch service, which produces a new branch
    record for every transition rather than mutating an existing one.

    Attributes:
        branch_id: The branch's unique identifier
        workspace_id: The identifier of the workspace the branch was
            created from
        name: The branch's human-readable, workspace-unique name
        base_revision: The workspace revision the branch started
            from, or None if no revision had ever been published for
            the workspace at creation time
        head_revision: The workspace revision the branch was most
            recently checked out against, or None if none is known
        status: The branch's current lifecycle state
    """

    branch_id: str

    workspace_id: str

    name: str

    base_revision: str | None

    head_revision: str | None

    status: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus

    def __post_init__(self):
        if self.branch_id is None or not self.branch_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                "Cannot build a branch with an empty or blank branch ID."
            )

        if self.workspace_id is None or not self.workspace_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                "Cannot build a branch with an empty or blank workspace ID."
            )

        if self.name is None or not self.name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                "Cannot build a branch with an empty or blank name."
            )

        if self.base_revision is not None and not self.base_revision.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                "Cannot build a branch with a blank base revision; omit it entirely instead."
            )

        if self.head_revision is not None and not self.head_revision.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                "Cannot build a branch with a blank head revision; omit it entirely instead."
            )

        if not isinstance(
            self.status,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                "Cannot build a branch: status must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus."
            )
