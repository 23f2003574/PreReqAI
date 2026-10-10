from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistry:
    """
    Immutable, centralised registry of consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding presets, addressed by preset identifier.

    The registry is a value object only. It performs no
    registration, no lookup, and no snapshot generation.
    Registration, lookup, and snapshot generation are the
    responsibility of a binding preset registry service.

    Attributes:
        presets: An immutable, order-preserving mapping of preset
            identifier to binding preset
    """

    presets: Mapping[
        str,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ]
