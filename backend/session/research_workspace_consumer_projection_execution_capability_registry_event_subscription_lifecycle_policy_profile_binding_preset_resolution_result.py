from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_resolution_result_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResultError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionSource,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResult:
    """
    Immutable outcome produced after resolving the effective binding
    preset, and its eligible member binding templates, for a preset
    identifier.

    The result is a value object only. It performs no resolution and
    no lookup. Resolution and lookup are the responsibility of a
    binding preset resolver.

    Attributes:
        preset: The effective preset that was resolved, or None if
            resolution failed
        templates: The preset's eligible member binding templates, in
            stored order, or an empty tuple if resolution failed
        resolved: Whether an effective preset was resolved
        source: Which source satisfied the resolution, or None if
            resolution failed
    """

    preset: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset
        | None
    )

    templates: tuple

    resolved: bool

    source: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionSource
        | None
    )

    def __post_init__(self):
        if self.resolved:
            if self.preset is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResultError(
                    "Cannot build a resolution result: a resolved result must carry a preset."
                )

            if not isinstance(
                self.source,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionSource,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResultError(
                    "Cannot build a resolution result: a resolved result must carry a known resolution source."
                )
        else:
            if self.preset is not None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResultError(
                    "Cannot build a resolution result: an unresolved result must not carry a preset."
                )

            if self.templates:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResultError(
                    "Cannot build a resolution result: an unresolved result must not carry templates."
                )

            if self.source is not None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResultError(
                    "Cannot build a resolution result: an unresolved result must not carry a resolution source."
                )
