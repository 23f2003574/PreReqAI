from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_checkpoint import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCheckpoint,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_checkpoint_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCheckpointError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_cursor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursor,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCheckpointBuilder:
    """
    Builds an immutable checkpoint capturing the synchronization
    state of a consumer projection execution capability registry
    event subscription resolution history traversal.

    The builder's responsibility is validation and capture of
    synchronization metadata, not navigation. It does NOT navigate
    history, restore bookmarks, replay sessions, mutate history,
    persist checkpoints, or inspect individual resolution sessions.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same history and cursor always produce the
      same checkpoint
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        history,

        cursor,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCheckpoint:
        """
        Build a checkpoint capturing a history's session count and a
        cursor's position.

        Args:
            history: The resolution history being traversed
            cursor: The cursor describing the current traversal
                position

        Returns:
            An immutable checkpoint

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCheckpointError:
                If the history or cursor is None, or the cursor's
                position exceeds history.session_count
        """

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCheckpointError(
                    "Cannot build a checkpoint for a None history."
                )
            )

        if not isinstance(

            history,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCheckpointError(
                    "Cannot build a checkpoint: history must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory."
                )
            )

        if cursor is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCheckpointError(
                    "Cannot build a checkpoint with a None cursor."
                )
            )

        if not isinstance(

            cursor,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursor,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCheckpointError(
                    "Cannot build a checkpoint: cursor must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursor."
                )
            )

        if cursor.position > history.session_count:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCheckpointError(
                    "Cannot build a checkpoint: cursor.position "
                    f"({cursor.position!r}) must not exceed "
                    "history.session_count "
                    f"({history.session_count!r})."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCheckpoint(
                session_count=history.session_count,

                last_position=cursor.position,

                is_empty=(
                    history.session_count == 0
                ),
            )
        )
