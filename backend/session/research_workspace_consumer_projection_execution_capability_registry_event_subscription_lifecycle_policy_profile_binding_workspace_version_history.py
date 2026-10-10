from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_version import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersion,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionHistory:
    """
    Immutable, chronologically ordered collection of every version
    ever published for a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace, together with a pointer to its current version.

    The history is a value object only. It performs no publication,
    no lookup, and no rollback. Publication, lookup, and rollback are
    the responsibility of a binding workspace version service.

    Attributes:
        workspace_id: The identifier of the workspace this history
            belongs to
        current_version: The version identifier currently in effect
            for the workspace
        versions: An immutable, order-preserving tuple of every
            version ever published for the workspace, in the order
            they were published
    """

    workspace_id: str

    current_version: str

    versions: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersion,
        ...,
    ]

    def __post_init__(self):
        if self.workspace_id is None or not self.workspace_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError(
                "Cannot build a workspace version history with an empty or blank workspace ID."
            )

        if self.current_version is None or not self.current_version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError(
                "Cannot build a workspace version history with an empty or blank current version."
            )

        if not self.versions:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError(
                "Cannot build a workspace version history with no versions."
            )

        if not any(version.version == self.current_version for version in self.versions):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError(
                f"Cannot build a workspace version history: current version {self.current_version!r} is not among its versions."
            )
