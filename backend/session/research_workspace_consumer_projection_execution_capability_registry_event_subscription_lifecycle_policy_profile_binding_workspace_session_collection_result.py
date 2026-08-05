from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_collection_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionResult:
    """
    Immutable report of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace session collection's membership size after it was
    modified.

    The result is a value object only. It performs no membership
    management. Adding and removing members are the responsibility of
    a session collection service.

    Attributes:
        collection_id: The identifier of the collection this result
            concerns
        member_count: How many sessions the collection holds after
            the operation that produced this result
    """

    collection_id: str

    member_count: int

    def __post_init__(self):
        if self.collection_id is None or not self.collection_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError(
                "Cannot build a session collection result with an empty or blank collection ID."
            )

        if (
            self.member_count is None
            or isinstance(self.member_count, bool)
            or not isinstance(self.member_count, int)
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError(
                "Cannot build a session collection result with a non-integer member_count."
            )

        if self.member_count < 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError(
                "Cannot build a session collection result with a negative member_count."
            )
