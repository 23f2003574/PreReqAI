from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_authorization_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationResult:
    """
    Immutable outcome of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution session authorization decision.

    The result is a value object only. It performs no authorization
    decision. Producing this outcome is the responsibility of a
    session authorization service.

    Attributes:
        authorized: Whether the requested operation is permitted
        reason: Why the operation was refused; always None when
            authorized is True, and always a non-blank explanation
            when authorized is False
    """

    authorized: bool

    reason: str = field(default=None)

    def __post_init__(self):
        if self.authorized is None or not isinstance(self.authorized, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError(
                "Cannot build an authorization result with a non-boolean authorized."
            )

        if self.authorized and self.reason is not None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError(
                "Cannot build an authorized authorization result with a reason."
            )

        if not self.authorized and (self.reason is None or not self.reason.strip()):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError(
                "Cannot build a denied authorization result with an empty or blank reason."
            )
