from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistry:
    """
    Immutable, centralised registry of consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspaces, addressed by workspace identifier.

    The registry is a value object only. It performs no
    registration, no lookup, and no snapshot generation.
    Registration, lookup, and snapshot generation are the
    responsibility of a binding workspace registry service.

    Attributes:
        workspaces: An immutable, order-preserving mapping of
            workspace identifier to binding workspace
    """

    workspaces: Mapping[
        str,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
    ]
