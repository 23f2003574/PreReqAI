from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistry:
    """
    Immutable, centralised registry of consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding templates, addressed by template identifier.

    The registry is a value object only. It performs no
    registration, no lookup, and no snapshot generation.
    Registration, lookup, and snapshot generation are the
    responsibility of a binding template registry service.

    Attributes:
        templates: An immutable, order-preserving mapping of template
            identifier to binding template
    """

    templates: Mapping[
        str,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ]
