from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_collection_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollection:
    """
    Immutable, point-in-time view of a named, reusable grouping of
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    sessions, so a caller can monitor or act on the group as a whole
    instead of one session at a time.

    The collection is a value object only. It performs no membership
    management. Creating collections and managing their membership
    are the responsibility of a session collection service.

    Attributes:
        collection_id: The collection's unique identifier
        name: The collection's human-readable name
        session_ids: The sessions currently in this collection, in
            the order they were added
    """

    collection_id: str

    name: str

    session_ids: tuple[str, ...]

    def __post_init__(self):
        if self.collection_id is None or not self.collection_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError(
                "Cannot build a session collection with an empty or blank collection ID."
            )

        if self.name is None or not self.name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError(
                "Cannot build a session collection with an empty or blank name."
            )

        if self.session_ids is None or not isinstance(self.session_ids, tuple):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError(
                "Cannot build a session collection with session_ids that is not a tuple."
            )

        for session_id in self.session_ids:
            if session_id is None or not isinstance(session_id, str) or not session_id.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError(
                    "Cannot build a session collection with an empty, blank, or non-string session ID."
                )
