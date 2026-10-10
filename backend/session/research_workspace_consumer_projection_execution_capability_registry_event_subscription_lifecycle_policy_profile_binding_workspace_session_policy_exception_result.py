from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_exception_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionResult:
    """
    Immutable outcome of an approval, revocation, or validation
    decision made against a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution session policy exception.

    The result is a value object only. It performs no decision.
    Producing this outcome is the responsibility of a session policy
    exception service.

    Attributes:
        approved: Whether the exception is currently usable
        reason: Why the exception is not usable; always None when
            approved is True, and always a non-blank explanation when
            approved is False
    """

    approved: bool

    reason: str = field(default=None)

    def __post_init__(self):
        if self.approved is None or not isinstance(self.approved, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError(
                "Cannot build a policy exception result with a non-boolean approved."
            )

        if self.approved and self.reason is not None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError(
                "Cannot build an approved policy exception result with a reason."
            )

        if not self.approved and (self.reason is None or not self.reason.strip()):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError(
                "Cannot build an unapproved policy exception result with an empty or blank reason."
            )
