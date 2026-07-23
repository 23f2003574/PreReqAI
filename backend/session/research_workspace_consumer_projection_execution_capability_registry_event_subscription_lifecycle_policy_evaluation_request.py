from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequest:
    """
    Immutable request supplied to a lifecycle policy evaluator,
    encapsulating a lifecycle policy and a proposed lifecycle
    transition.

    The request is a value object only. It performs no evaluation of
    the transition against the policy, no validation of the
    transition, and no mutation of either the policy or the
    transition.

    Attributes:
        policy: The lifecycle policy to evaluate against
        transition: The proposed lifecycle transition being evaluated
    """

    policy: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy
    )

    transition: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition
    )
