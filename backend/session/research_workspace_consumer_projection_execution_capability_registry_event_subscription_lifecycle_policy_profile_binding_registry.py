from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistry:
    """
    Immutable, centralised registry of consumer projection execution
    capability registry event subscription lifecycle policy profile
    bindings, addressed by binding identifier.

    The registry is a value object only. It performs no registration,
    no lookup, and no snapshot generation. Registration, lookup, and
    snapshot generation are the responsibility of a binding registry
    service.

    Attributes:
        bindings: An immutable, order-preserving mapping of binding
            identifier to profile binding
    """

    bindings: Mapping[
        str,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ]
