from dataclasses import (
    dataclass,
)

from datetime import datetime

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_checkpoint_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpoint:
    """
    Immutable, point-in-time snapshot of a consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding workspace execution session's runtime
    state, taken after a stage finishes successfully so an
    interrupted run can resume from it instead of restarting.

    The checkpoint is a value object only. It performs no
    checkpointing or restoration. Creating, restoring, and removing
    checkpoints are the responsibility of a session checkpoint
    service.

    Attributes:
        checkpoint_id: The checkpoint's unique identifier
        session_id: The identifier of the execution session this
            checkpoint was taken for
        stage_id: The identifier of the stage whose successful
            completion this checkpoint was taken after
        state: The runtime state captured at this checkpoint
        created_at: When this checkpoint was taken
    """

    checkpoint_id: str

    session_id: str

    stage_id: str

    state: Mapping

    created_at: datetime

    def __post_init__(self):
        if self.checkpoint_id is None or not self.checkpoint_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError(
                "Cannot build a session checkpoint with an empty or blank checkpoint ID."
            )

        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError(
                "Cannot build a session checkpoint with an empty or blank session ID."
            )

        if self.stage_id is None or not self.stage_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError(
                "Cannot build a session checkpoint with an empty or blank stage ID."
            )

        if self.state is None or not isinstance(self.state, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError(
                "Cannot build a session checkpoint with state that is not a mapping."
            )

        if self.created_at is None or not isinstance(self.created_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError(
                "Cannot build a session checkpoint with a non-datetime created_at."
            )
