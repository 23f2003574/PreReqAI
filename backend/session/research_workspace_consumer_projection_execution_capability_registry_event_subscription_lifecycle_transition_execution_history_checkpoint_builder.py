from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_checkpoint import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCheckpoint,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_checkpoint_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCheckpointError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_cursor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursor,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCheckpointBuilder:
    """
    Builds an immutable checkpoint capturing the synchronization
    state of a consumer projection execution capability registry
    event subscription lifecycle transition execution history
    traversal.

    The builder's responsibility is validation and capture of
    synchronization metadata, not navigation. It does NOT navigate
    history, replay transitions, read history entries, modify
    history, restore cursors, persist checkpoints, log, or compute
    metrics.

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

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCheckpoint:
        """
        Build a checkpoint capturing a history's entry count and a
        cursor's position.

        Args:
            history: The execution history being traversed
            cursor: The cursor describing the current traversal
                position

        Returns:
            An immutable checkpoint

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCheckpointError:
                If the history or cursor is None, or the cursor's
                position exceeds history.entry_count
        """

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCheckpointError(
                    "Cannot build a checkpoint for a None history."
                )
            )

        if not isinstance(

            history,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistory,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCheckpointError(
                    "Cannot build a checkpoint: history must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistory."
                )
            )

        if cursor is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCheckpointError(
                    "Cannot build a checkpoint with a None cursor."
                )
            )

        if not isinstance(

            cursor,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursor,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCheckpointError(
                    "Cannot build a checkpoint: cursor must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursor."
                )
            )

        if cursor.position > history.entry_count:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCheckpointError(
                    "Cannot build a checkpoint: cursor.position "
                    f"({cursor.position!r}) must not exceed "
                    "history.entry_count "
                    f"({history.entry_count!r})."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCheckpoint(
                entry_count=history.entry_count,

                last_position=cursor.position,

                is_empty=(
                    history.entry_count == 0
                ),
            )
        )
