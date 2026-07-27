from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_inheritance import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritance,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceResult:
    """
    Immutable result representing the resolved effective profile and the
    inheritance chain leading to it.

    Attributes:
        effective_profile_id: The identifier of the resolved active profile,
            or None if no profile is active.
        inherited: True if the profile was resolved via inheritance from a parent,
            False if it was assigned directly to the target.
        inheritance_chain: An immutable, order-preserving tuple of inheritance relations
            leading to the resolved profile.
    """

    effective_profile_id: str | None

    inherited: bool

    inheritance_chain: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritance,
        ...,
    ]
