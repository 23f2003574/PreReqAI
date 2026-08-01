from dataclasses import (
    dataclass,
)


from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset:
    """
    Immutable record describing a reusable, named grouping of
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding templates, so that
    common binding configurations can be provisioned together instead
    of one binding template at a time.

    The preset is a value object only. It performs no registration
    and no instantiation. Registration, replacement, removal,
    lookup, and instantiation are the responsibility of a binding
    preset service.

    Attributes:
        preset_id: The preset's unique identifier
        name: The preset's human-readable name
        description: A human-readable description of the preset
        binding_template_ids: The identifiers of the binding
            templates the preset is built from, in deterministic
            order
    """

    preset_id: str

    name: str

    description: str | None

    binding_template_ids: tuple

    def __post_init__(self):
        if self.preset_id is None or not self.preset_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError(
                "Cannot build a binding preset with an empty or blank preset ID."
            )

        if self.name is None or not self.name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError(
                "Cannot build a binding preset with an empty or blank name."
            )

        if self.binding_template_ids is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError(
                "Cannot build a binding preset with None binding template IDs."
            )

        for template_id in self.binding_template_ids:
            if template_id is None or not template_id.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError(
                    "Cannot build a binding preset with an empty or blank member binding template ID."
                )
