from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_resolution_result_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResultError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionSource,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResult:
    """
    Immutable outcome produced after resolving the effective binding
    group, and its eligible member bindings, for a group identifier.

    The result is a value object only. It performs no resolution and
    no lookup. Resolution and lookup are the responsibility of a
    binding group resolver.

    Attributes:
        group: The effective group that was resolved, or None if
            resolution failed
        bindings: The group's eligible member bindings, in stored
            order, or an empty tuple if resolution failed
        resolved: Whether an effective group was resolved
        source: Which source satisfied the resolution, or None if
            resolution failed
    """

    group: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup
        | None
    )

    bindings: tuple

    resolved: bool

    source: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionSource
        | None
    )

    def __post_init__(self):
        if self.resolved:
            if self.group is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResultError(
                    "Cannot build a resolution result: a resolved result must carry a group."
                )

            if not isinstance(
                self.source,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionSource,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResultError(
                    "Cannot build a resolution result: a resolved result must carry a known resolution source."
                )
        else:
            if self.group is not None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResultError(
                    "Cannot build a resolution result: an unresolved result must not carry a group."
                )

            if self.bindings:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResultError(
                    "Cannot build a resolution result: an unresolved result must not carry bindings."
                )

            if self.source is not None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResultError(
                    "Cannot build a resolution result: an unresolved result must not carry a resolution source."
                )
