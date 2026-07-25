from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionSource,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionResult:
    """
    Immutable outcome produced after resolving a consumer projection
    execution capability registry event subscription lifecycle
    policy template by identifier.

    The result is a value object only. It performs no resolution
    and no lookup. Resolution and lookup are the responsibility of
    a template resolver.

    Attributes:
        resolved_template: The template that was resolved, or None
            if resolution failed
        resolution_successful: Whether a template was resolved
        resolution_source: Which source satisfied the resolution, or
            None if resolution failed
    """

    resolved_template: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate
        | None
    )

    resolution_successful: bool

    resolution_source: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionSource
        | None
    )
