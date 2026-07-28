from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_resolution_result_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResultError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionSource,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResult:
    """
    Immutable outcome produced after resolving the effective profile
    binding for an execution capability identifier.

    The result is a value object only. It performs no resolution and
    no lookup. Resolution and lookup are the responsibility of a
    binding resolver.

    Attributes:
        capability_id: The identifier of the capability for which
            resolution was attempted
        binding: The effective binding that was resolved, or None if
            resolution failed
        resolved: Whether an effective binding was resolved
        source: Which source satisfied the resolution, or None if
            resolution failed
    """

    capability_id: str

    binding: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding
        | None
    )

    resolved: bool

    source: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionSource
        | None
    )

    def __post_init__(self):
        if self.resolved:
            if self.binding is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResultError(
                    "Cannot build a resolution result: a resolved result must carry a binding."
                )

            if not isinstance(
                self.source,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionSource,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResultError(
                    "Cannot build a resolution result: a resolved result must carry a known resolution source."
                )
        else:
            if self.binding is not None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResultError(
                    "Cannot build a resolution result: an unresolved result must not carry a binding."
                )

            if self.source is not None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResultError(
                    "Cannot build a resolution result: an unresolved result must not carry a resolution source."
                )
