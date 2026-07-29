from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersion:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    group's membership at the moment it was published, so a
    deployment can target a stable snapshot instead of the group's
    mutable, current definition.

    The version is a value object only. It performs no publication,
    lookup, or rollback. Publication, lookup, and rollback are the
    responsibility of a binding group version service.

    Attributes:
        version: The version's unique identifier
        binding_ids: The identifiers of the group's member bindings
            at the moment this version was published, in stored order
        created_at: When this version was published
    """

    version: str

    binding_ids: tuple

    created_at: datetime

    def __post_init__(self):
        if self.version is None or not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError(
                "Cannot build a group version with an empty or blank version."
            )

        if self.binding_ids is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError(
                "Cannot build a group version with None binding IDs."
            )

        if self.created_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError(
                "Cannot build a group version with a None created_at timestamp."
            )
