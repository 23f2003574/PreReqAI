from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_sync_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncRequest:
    """
    Immutable request description for synchronizing a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace's current definition,
    versions, and release metadata to a single target registry,
    deployment target, or runtime cache.

    The request is a value object only. It performs no lookup and no
    synchronization. Lookup and synchronization are the
    responsibility of a synchronization service.

    Attributes:
        workspace_id: The identifier of the workspace to synchronize
        operation: The sync operation, either "register" to push the
            workspace's current state to the target, or "remove" to
            remove the workspace's state from the target
        target: The identifier of the target registry, deployment
            target, or runtime cache to synchronize
    """

    workspace_id: str

    operation: str

    target: str

    def __post_init__(self):
        if self.workspace_id is None or not self.workspace_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError(
                "Cannot build a sync request with an empty or blank workspace ID."
            )

        if self.operation is None or not self.operation.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError(
                "Cannot build a sync request with an empty or blank operation."
            )

        if self.operation not in ("register", "remove"):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError(
                f"Invalid sync request operation {self.operation!r}. Must be 'register' or 'remove'."
            )

        if self.target is None or not self.target.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError(
                "Cannot build a sync request with an empty or blank target."
            )
