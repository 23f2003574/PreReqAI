from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_ownership_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionTransferResult:
    """
    Immutable outcome of transferring ownership of a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution session from
    one worker or coordinator to another.

    The result is a value object only. It performs no transfer.
    Transferring ownership is the responsibility of a session
    ownership service.

    Attributes:
        session_id: The identifier of the session that was
            transferred
        previous_owner: The identifier of the owner the session was
            transferred away from
        current_owner: The identifier of the owner the session was
            transferred to
        transferred: Whether the transfer succeeded
    """

    session_id: str

    previous_owner: str

    current_owner: str

    transferred: bool

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError(
                "Cannot build a session transfer result with an empty or blank session ID."
            )

        if self.previous_owner is None or not self.previous_owner.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError(
                "Cannot build a session transfer result with an empty or blank previous_owner."
            )

        if self.current_owner is None or not self.current_owner.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError(
                "Cannot build a session transfer result with an empty or blank current_owner."
            )

        if self.transferred is None or not isinstance(self.transferred, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError(
                "Cannot build a session transfer result with a non-boolean transferred."
            )
