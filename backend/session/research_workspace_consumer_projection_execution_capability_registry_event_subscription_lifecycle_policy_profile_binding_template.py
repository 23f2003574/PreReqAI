from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate:
    """
    Immutable record describing a reusable consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding configuration, so that standardized
    bindings can be instantiated instead of repeatedly created from
    scratch.

    The template is a value object only. It performs no registration
    and no instantiation. Registration, replacement, removal,
    lookup, and instantiation are the responsibility of a binding
    template service.

    Attributes:
        template_id: The template's unique identifier
        name: The template's human-readable name
        binding_ids: The identifiers of the bindings the template is
            built from, in deterministic order
        metadata: An immutable mapping of descriptive information
            about the template
    """

    template_id: str

    name: str

    binding_ids: tuple

    metadata: Mapping[str, object]

    def __post_init__(self):
        if self.template_id is None or not self.template_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError(
                "Cannot build a binding template with an empty or blank template ID."
            )

        if self.name is None or not self.name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError(
                "Cannot build a binding template with an empty or blank name."
            )

        if self.binding_ids is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError(
                "Cannot build a binding template with None binding IDs."
            )

        for binding_id in self.binding_ids:
            if binding_id is None or not binding_id.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError(
                    "Cannot build a binding template with an empty or blank member binding ID."
                )

        if self.metadata is None or not isinstance(self.metadata, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError(
                "Cannot build a binding template with invalid metadata; a mapping is required."
            )
