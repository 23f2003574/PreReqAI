from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistry:
    """
    Immutable registry of active consumer projection execution
    capability registry event subscription lifecycle policy profile
    assignments, addressed by target identifier.

    The registry is a value object only. It performs no registration,
    no lookup, and no snapshot generation. Registration, lookup, and
    snapshot generation are the responsibility of an assignment
    registry service.

    Attributes:
        assignments: An immutable, order-preserving mapping of target
            identifier to the currently active profile assignment for
            that target
    """

    assignments: Mapping[
        str,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
    ]
