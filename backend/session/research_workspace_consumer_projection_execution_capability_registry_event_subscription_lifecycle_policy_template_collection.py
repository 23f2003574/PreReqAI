from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCollection:
    """
    Immutable collection of consumer projection execution
    capability registry event subscription lifecycle policy
    templates, addressed by template identifier.

    The collection is a value object only. It performs no
    registration, no lookup, and no instantiation of its templates.
    Registration, lookup, and instantiation are the responsibility
    of a template service.

    Attributes:
        templates: An immutable, order-preserving mapping of
            template identifier to lifecycle policy template
    """

    templates: Mapping[
        str,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
    ]
