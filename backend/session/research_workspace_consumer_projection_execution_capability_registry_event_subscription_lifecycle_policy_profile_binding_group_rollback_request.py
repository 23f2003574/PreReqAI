from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_rollback_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest:
    """
    Immutable request to restore a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding group to the state recorded by a specific deployment.

    The request is a value object only. It performs no lookup, no
    verification, and no rollback. Lookup, verification, and
    rollback are the responsibility of a rollback service.

    Attributes:
        group_id: The identifier of the group to roll back
        deployment_id: The identifier of the recorded deployment
            whose state should be restored
    """

    group_id: str

    deployment_id: str

    def __post_init__(self):
        if self.group_id is None or not self.group_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError(
                "Cannot build a rollback request with an empty or blank group ID."
            )

        if self.deployment_id is None or not self.deployment_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError(
                "Cannot build a rollback request with an empty or blank deployment ID."
            )
