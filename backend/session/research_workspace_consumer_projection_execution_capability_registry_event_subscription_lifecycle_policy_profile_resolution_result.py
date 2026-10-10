from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_resolution_result_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResultError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionSource,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResult:
    """
    Immutable outcome produced after resolving a consumer projection
    execution capability registry event subscription lifecycle
    policy profile by identifier.

    The result is a value object only. It performs no resolution
    and no lookup. Resolution and lookup are the responsibility of
    a profile resolver.

    Attributes:
        profile: The profile that was resolved, or None if
            resolution failed
        resolved: Whether a profile was resolved
        resolution_source: Which source satisfied the resolution, or
            None if resolution failed
    """

    profile: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile
        | None
    )

    resolved: bool

    resolution_source: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionSource
        | None
    )

    def __post_init__(self):

        if self.resolved:

            if self.profile is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResultError(
                        "Cannot build a resolution result: a resolved "
                        "result must carry a profile."
                    )
                )

            if not isinstance(

                self.resolution_source,

                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionSource,
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResultError(
                        "Cannot build a resolution result: a resolved "
                        "result must carry a known resolution source."
                    )
                )

        else:

            if self.profile is not None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResultError(
                        "Cannot build a resolution result: an unresolved "
                        "result must not carry a profile."
                    )
                )

            if self.resolution_source is not None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResultError(
                        "Cannot build a resolution result: an unresolved "
                        "result must not carry a resolution source."
                    )
                )
