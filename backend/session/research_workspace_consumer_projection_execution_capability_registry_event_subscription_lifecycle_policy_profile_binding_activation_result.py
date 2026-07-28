from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationResult:
    """
    Immutable outcome produced after transitioning a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding's activation state.

    Attributes:
        binding_id: The identifier of the binding that was
            transitioned
        previous_state: The state the binding held immediately before
            the transition
        current_state: The state the binding holds after the
            transition
        activated_at: When the binding became (or is scheduled to
            become) active, or None if the binding is INACTIVE
    """

    binding_id: str

    previous_state: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState
    )

    current_state: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState
    )

    activated_at: (
        datetime | None
    )
