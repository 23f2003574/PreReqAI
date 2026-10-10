from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_sync_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncRequest:
    """
    Immutable request description for synchronizing a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding group's current state to a
    single target registry, deployment target, or runtime cache.

    The request is a value object only. It performs no lookup and no
    synchronization. Lookup and synchronization are the
    responsibility of a synchronization service.

    Attributes:
        group_id: The identifier of the group to synchronize
        operation: The sync operation, either "register" to push the
            group's current state to the target, or "remove" to
            remove the group's state from the target
        target: The identifier of the target registry, deployment
            target, or runtime cache to synchronize
    """

    group_id: str

    operation: str

    target: str

    def __post_init__(self):
        if self.group_id is None or not self.group_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError(
                "Cannot build a sync request with an empty or blank group ID."
            )

        if self.operation is None or not self.operation.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError(
                "Cannot build a sync request with an empty or blank operation."
            )

        if self.operation not in ("register", "remove"):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError(
                f"Invalid sync request operation {self.operation!r}. Must be 'register' or 'remove'."
            )

        if self.target is None or not self.target.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError(
                "Cannot build a sync request with an empty or blank target."
            )
