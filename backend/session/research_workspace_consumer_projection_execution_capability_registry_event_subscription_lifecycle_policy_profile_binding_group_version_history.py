from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_version import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersion,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionHistory:
    """
    Immutable, chronologically ordered collection of every version
    ever published for a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    group, together with a pointer to its current version.

    The history is a value object only. It performs no publication,
    no lookup, and no rollback. Publication, lookup, and rollback are
    the responsibility of a binding group version service.

    Attributes:
        group_id: The identifier of the group this history belongs to
        current_version: The version identifier currently in effect
            for the group
        versions: An immutable, order-preserving tuple of every
            version ever published for the group, in the order they
            were published
    """

    group_id: str

    current_version: str

    versions: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersion,
        ...,
    ]

    def __post_init__(self):
        if self.group_id is None or not self.group_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError(
                "Cannot build a group version history with an empty or blank group ID."
            )

        if self.current_version is None or not self.current_version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError(
                "Cannot build a group version history with an empty or blank current version."
            )

        if not self.versions:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError(
                "Cannot build a group version history with no versions."
            )

        if not any(version.version == self.current_version for version in self.versions):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError(
                f"Cannot build a group version history: current version {self.current_version!r} is not among its versions."
            )
