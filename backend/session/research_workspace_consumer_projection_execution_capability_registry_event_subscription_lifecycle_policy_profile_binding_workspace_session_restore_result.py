from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_checkpoint_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRestoreResult:
    """
    Immutable outcome of restoring a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution session from one of its checkpoints.

    The result is a value object only. It performs no restoration.
    Restoring a session is the responsibility of a session checkpoint
    service.

    Attributes:
        session_id: The identifier of the session that was restored
        checkpoint_id: The identifier of the checkpoint restored from
        restored: Whether the restoration succeeded
    """

    session_id: str

    checkpoint_id: str

    restored: bool

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError(
                "Cannot build a session restore result with an empty or blank session ID."
            )

        if self.checkpoint_id is None or not self.checkpoint_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError(
                "Cannot build a session restore result with an empty or blank checkpoint ID."
            )

        if self.restored is None or not isinstance(self.restored, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError(
                "Cannot build a session restore result with a non-boolean restored."
            )
