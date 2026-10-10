from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistry:
    """
    Immutable, centralised registry of consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding groups, addressed by group identifier.

    The registry is a value object only. It performs no registration,
    no lookup, and no snapshot generation. Registration, lookup, and
    snapshot generation are the responsibility of a binding group
    registry service.

    Attributes:
        groups: An immutable, order-preserving mapping of group
            identifier to binding group
    """

    groups: Mapping[
        str,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
    ]
