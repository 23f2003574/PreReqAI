from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_version import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionHistory:
    """
    Immutable record of every version published for a single
    consumer projection execution capability registry event
    subscription lifecycle policy profile, and which of those
    versions is current.

    The history is a value object only. It performs no publication,
    no lookup, and no rollback. Publication, lookup, and rollback are
    the responsibility of a profile version service.

    Attributes:
        profile_id: The identifier of the profile this history
            belongs to
        current_version: The version identifier the profile is
            currently at. This may be earlier than the most recently
            published version after a rollback, since a rollback
            never removes versions from history.
        versions: An immutable, order-preserving tuple of every
            version ever published for this profile, in publication
            order
    """

    profile_id: str

    current_version: str

    versions: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
        ...,
    ]
