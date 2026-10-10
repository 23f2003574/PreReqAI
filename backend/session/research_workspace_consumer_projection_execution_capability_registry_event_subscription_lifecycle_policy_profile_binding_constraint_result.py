from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_constraint import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraint,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintResult:
    """
    Immutable outcome produced after evaluating every constraint
    registered for a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    against a runtime context.

    Attributes:
        satisfied: Whether every registered constraint passed and the
            binding is active
        failed_constraints: An immutable, order-preserving tuple of
            every constraint that failed, empty if the binding is
            satisfied
    """

    satisfied: bool

    failed_constraints: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraint,
        ...,
    ]
