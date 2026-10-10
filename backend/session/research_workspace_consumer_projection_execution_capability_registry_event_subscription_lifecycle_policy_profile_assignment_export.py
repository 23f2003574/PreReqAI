from dataclasses import (
    dataclass,
)

from datetime import datetime

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_serialization_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentExport:
    """
    Immutable, transferable representation of consumer projection
    execution capability registry event subscription lifecycle
    policy profile assignments, suitable for persistence and transfer
    between registries, environments, and deployments.

    The export is a value object only. It performs no assignment
    lookup and no cross-checking against a profile registry.

    Attributes:
        exported_at: When the export was captured
        assignments: An immutable, order-preserving tuple of the
            exported assignment records
        metadata: An immutable mapping of descriptive information
            about the export
    """

    exported_at: datetime

    assignments: tuple

    metadata: Mapping[str, object]

    def __post_init__(self):
        if self.exported_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError(
                "Cannot build an export with a None exported_at timestamp."
            )

        if self.assignments is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError(
                "Cannot build an export with None assignments."
            )

        if self.metadata is None or not isinstance(self.metadata, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError(
                "Cannot build an export with invalid metadata; a mapping is required."
            )
