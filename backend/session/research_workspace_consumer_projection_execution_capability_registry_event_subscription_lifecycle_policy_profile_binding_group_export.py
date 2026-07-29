from dataclasses import (
    dataclass,
)

from datetime import datetime

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_serialization_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupExport:
    """
    Immutable, transferable representation of consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding groups, suitable for persistence and
    transfer between registries, environments, and deployments.

    The export is a value object only. It performs no group lookup
    and no cross-checking against a binding registry.

    Attributes:
        exported_at: When the export was captured
        groups: An immutable, order-preserving tuple of the exported
            binding groups
        metadata: An immutable mapping of descriptive information
            about the export
    """

    exported_at: datetime

    groups: tuple

    metadata: Mapping[str, object]

    def __post_init__(self):
        if self.exported_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError(
                "Cannot build an export with a None exported_at timestamp."
            )

        if self.groups is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError(
                "Cannot build an export with None groups."
            )

        if self.metadata is None or not isinstance(self.metadata, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError(
                "Cannot build an export with invalid metadata; a mapping is required."
            )
