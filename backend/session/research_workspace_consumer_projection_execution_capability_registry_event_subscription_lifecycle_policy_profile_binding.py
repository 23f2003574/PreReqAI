from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding:
    """
    Immutable record binding a consumer projection execution
    capability registry event subscription lifecycle policy profile
    to an execution capability, enabling a reusable profile-to-
    capability mapping.

    The binding is a value object only. It performs no binding
    logic. Binding and unbinding are the responsibility of a binding
    service, which produces a new binding record for every bind
    rather than mutating an existing one.

    Attributes:
        binding_id: The binding's unique identifier
        profile_id: The identifier of the bound profile
        capability_id: The identifier of the execution capability
            the profile is bound to
        created_at: When the binding was created
    """

    binding_id: str

    profile_id: str

    capability_id: str

    created_at: datetime

    def __post_init__(self):
        if self.binding_id is None or not self.binding_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError(
                "Cannot build a binding with an empty or blank binding ID."
            )

        if self.profile_id is None or not self.profile_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError(
                "Cannot build a binding with an empty or blank profile ID."
            )

        if self.capability_id is None or not self.capability_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError(
                "Cannot build a binding with an empty or blank capability ID."
            )

        if self.created_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError(
                "Cannot build a binding with a None created_at timestamp."
            )
