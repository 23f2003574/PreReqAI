from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_admission_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionResult:
    """
    Immutable outcome of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution session admission decision.

    The result is a value object only. It performs no admission
    decision. Producing this outcome is the responsibility of a
    session admission service.

    Attributes:
        accepted: Whether the session may start
        reason: Why the session was refused; always None when
            accepted is True, and always a non-blank explanation when
            accepted is False
    """

    accepted: bool

    reason: str = field(default=None)

    def __post_init__(self):
        if self.accepted is None or not isinstance(self.accepted, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError(
                "Cannot build an admission result with a non-boolean accepted."
            )

        if self.accepted and self.reason is not None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError(
                "Cannot build an accepted admission result with a reason."
            )

        if not self.accepted and (self.reason is None or not self.reason.strip()):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError(
                "Cannot build a rejected admission result with an empty or blank reason."
            )
