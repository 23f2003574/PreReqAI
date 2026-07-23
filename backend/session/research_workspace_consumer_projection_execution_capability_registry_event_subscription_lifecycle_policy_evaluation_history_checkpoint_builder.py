from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_history_checkpoint import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpoint,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_history_checkpoint_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointBuilder:
    """
    Builds an immutable checkpoint capturing the synchronization
    state of a consumer projection execution capability registry
    event subscription lifecycle policy evaluation history
    traversal.

    The builder's responsibility is validation and capture of
    synchronization metadata, not navigation. It does NOT navigate
    history, replay evaluations, read history entries, evaluate
    policies, modify history, restore cursors, persist checkpoints,
    log, or compute metrics.

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

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpoint:
        """
        Build a checkpoint capturing a history's entry count and a
        cursor's position.

        Args:
            history: The evaluation history being traversed
            cursor: The cursor describing the current traversal
                position

        Returns:
            An immutable checkpoint

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointError:
                If the history or cursor is None, or the cursor's
                position exceeds history.entry_count
        """

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointError(
                    "Cannot build a checkpoint for a None history."
                )
            )

        if cursor is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointError(
                    "Cannot build a checkpoint with a None cursor."
                )
            )

        if cursor.position > history.entry_count:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointError(
                    "Cannot build a checkpoint: cursor.position "
                    f"({cursor.position!r}) must not exceed "
                    "history.entry_count "
                    f"({history.entry_count!r})."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpoint(
                entry_count=history.entry_count,

                last_position=cursor.position,

                is_empty=(
                    history.entry_count == 0
                ),
            )
        )
