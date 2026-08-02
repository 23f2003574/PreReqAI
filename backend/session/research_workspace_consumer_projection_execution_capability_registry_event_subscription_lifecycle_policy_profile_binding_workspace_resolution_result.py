from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_resolution_result_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionResultError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionSource,
)


_EXPECTED_RESOURCE_KINDS = frozenset({"bindings", "templates", "presets", "groups"})


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionResult:
    """
    Immutable outcome produced after resolving the effective binding
    workspace, and the counts of its eligible member resources, for a
    workspace identifier.

    The result is a value object only. It performs no resolution and
    no lookup. Resolution and lookup are the responsibility of a
    binding workspace resolver.

    Attributes:
        workspace: The effective workspace that was resolved, or None
            if resolution failed
        resolved: Whether an effective workspace was resolved
        resource_counts: An immutable mapping of resource kind
            ("bindings", "templates", "presets", "groups") to the
            number of that kind of eligible member resource on the
            workspace, or an empty mapping if resolution failed
        source: Which source satisfied the resolution, or None if
            resolution failed
    """

    workspace: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace
        | None
    )

    resolved: bool

    resource_counts: Mapping[str, int]

    source: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionSource
        | None
    )

    def __post_init__(self):
        if self.resolved:
            if self.workspace is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionResultError(
                    "Cannot build a resolution result: a resolved result must carry a workspace."
                )

            if not isinstance(
                self.source,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionSource,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionResultError(
                    "Cannot build a resolution result: a resolved result must carry a known resolution source."
                )

            if set(self.resource_counts) != _EXPECTED_RESOURCE_KINDS:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionResultError(
                    "Cannot build a resolution result: a resolved result must carry counts for every resource kind."
                )
        else:
            if self.workspace is not None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionResultError(
                    "Cannot build a resolution result: an unresolved result must not carry a workspace."
                )

            if self.resource_counts:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionResultError(
                    "Cannot build a resolution result: an unresolved result must not carry resource counts."
                )

            if self.source is not None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionResultError(
                    "Cannot build a resolution result: an unresolved result must not carry a resolution source."
                )
