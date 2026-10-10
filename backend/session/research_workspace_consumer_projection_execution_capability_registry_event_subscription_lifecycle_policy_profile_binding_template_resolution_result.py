from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_resolution_result_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResultError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionSource,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResult:
    """
    Immutable outcome produced after resolving the effective binding
    template, and its eligible member bindings, for a template
    identifier.

    The result is a value object only. It performs no resolution and
    no lookup. Resolution and lookup are the responsibility of a
    binding template resolver.

    Attributes:
        template: The effective template that was resolved, or None
            if resolution failed
        bindings: The template's eligible member bindings, in stored
            order, or an empty tuple if resolution failed
        resolved: Whether an effective template was resolved
        source: Which source satisfied the resolution, or None if
            resolution failed
    """

    template: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate
        | None
    )

    bindings: tuple

    resolved: bool

    source: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionSource
        | None
    )

    def __post_init__(self):
        if self.resolved:
            if self.template is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResultError(
                    "Cannot build a resolution result: a resolved result must carry a template."
                )

            if not isinstance(
                self.source,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionSource,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResultError(
                    "Cannot build a resolution result: a resolved result must carry a known resolution source."
                )
        else:
            if self.template is not None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResultError(
                    "Cannot build a resolution result: an unresolved result must not carry a template."
                )

            if self.bindings:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResultError(
                    "Cannot build a resolution result: an unresolved result must not carry bindings."
                )

            if self.source is not None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResultError(
                    "Cannot build a resolution result: an unresolved result must not carry a resolution source."
                )
