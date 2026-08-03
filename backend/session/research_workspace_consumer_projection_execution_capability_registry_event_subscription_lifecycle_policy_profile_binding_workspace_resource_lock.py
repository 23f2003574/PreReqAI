from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_lock_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResourceLock:
    """
    Immutable record of exclusive access held by one consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution pipeline
    over a single workspace resource.

    The lock is a value object only. It performs no acquisition, no
    release, and no expiration. Acquisition, release, and expiration
    are the responsibility of a workspace lock service.

    Attributes:
        lock_id: The lock's unique identifier
        resource_type: The kind of resource held, for example
            "binding" or "workspace"
        resource_id: The identifier of the specific resource held
        pipeline_id: The identifier of the pipeline holding the lock
        acquired_at: When the lock was acquired
        expires_at: When the lock automatically expires; must be
            after acquired_at
    """

    lock_id: str

    resource_type: str

    resource_id: str

    pipeline_id: str

    acquired_at: datetime

    expires_at: datetime

    def __post_init__(self):
        if self.lock_id is None or not self.lock_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError(
                "Cannot build a workspace resource lock with an empty or blank lock ID."
            )

        if self.resource_type is None or not self.resource_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError(
                "Cannot build a workspace resource lock with an empty or blank resource type."
            )

        if self.resource_id is None or not self.resource_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError(
                "Cannot build a workspace resource lock with an empty or blank resource ID."
            )

        if self.pipeline_id is None or not self.pipeline_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError(
                "Cannot build a workspace resource lock with an empty or blank pipeline ID."
            )

        if self.acquired_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError(
                "Cannot build a workspace resource lock with a None acquired_at."
            )

        if self.expires_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError(
                "Cannot build a workspace resource lock with a None expires_at."
            )

        if self.expires_at <= self.acquired_at:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError(
                "Cannot build a workspace resource lock with an expires_at that is not after acquired_at."
            )
