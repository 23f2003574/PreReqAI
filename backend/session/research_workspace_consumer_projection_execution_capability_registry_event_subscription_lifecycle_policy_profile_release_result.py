from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_release import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRelease,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseResult:
    """
    Immutable outcome produced after transitioning a consumer
    projection execution capability registry event subscription
    lifecycle policy profile version's release status.

    The result is a value object only. It performs no transition
    logic. Transitions are the responsibility of a release service.

    Attributes:
        previous_status: The status the version held immediately
            before the transition
        current_status: The status the version holds after the
            transition
        release: The resulting release record
    """

    previous_status: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus
    )

    current_status: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus
    )

    release: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRelease
    )
