from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_lock_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_resource_lock import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResourceLock,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockResult:
    """
    Immutable outcome produced after attempting to acquire a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace resource
    lock.

    The result is a value object only. It performs no acquisition.
    Acquisition is the responsibility of a workspace lock service.

    Attributes:
        acquired: Whether the lock was acquired; False when the
            resource was already actively locked by another pipeline
        reason: Why acquisition succeeded or failed
        lock: The held lock, present when acquired is True and absent
            otherwise
    """

    acquired: bool

    reason: str

    lock: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResourceLock = None

    def __post_init__(self):
        if not isinstance(self.acquired, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError(
                "Cannot build a workspace lock result with a non-boolean acquired flag."
            )

        if self.reason is None or not self.reason.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError(
                "Cannot build a workspace lock result with an empty or blank reason."
            )

        if self.acquired and not isinstance(self.lock, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResourceLock):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError(
                "Cannot build a workspace lock result: an acquired result must carry a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResourceLock."
            )

        if not self.acquired and self.lock is not None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError(
                "Cannot build a workspace lock result: an unacquired result must not carry a lock."
            )
