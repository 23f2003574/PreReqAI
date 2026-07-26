from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistry:
    """
    Immutable collection of consumer projection execution
    capability registry event subscription lifecycle policy
    profiles, addressed by profile identifier and managed
    independently from any runtime lifecycle policy.

    The registry is a value object only. It performs no
    registration, no lookup, and no snapshot generation.
    Registration, lookup, and snapshot generation are the
    responsibility of a profile registry service.

    Attributes:
        profiles: An immutable, order-preserving mapping of profile
            identifier to lifecycle policy profile
    """

    profiles: Mapping[
        str,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ]
