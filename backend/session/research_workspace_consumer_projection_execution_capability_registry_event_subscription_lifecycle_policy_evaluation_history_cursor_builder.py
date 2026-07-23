from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_history_cursor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCursor,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_history_cursor_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCursorError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCursorBuilder:
    """
    Builds an immutable cursor representing a position within a
    consumer projection execution capability registry event
    subscription lifecycle policy evaluation history.

    The builder's responsibility is validation and computation of
    traversal state, not navigation. It does NOT navigate history,
    replay evaluations, modify history, inspect individual history
    entries, filter history, persist cursors, log, or compute
    metrics - only history.entry_count is consulted.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same history and position always produce the
      same cursor
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        history,

        position,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCursor:
        """
        Build a cursor for a position within an evaluation history.

        Args:
            history: The evaluation history to build a cursor
                against
            position: The position within the history, from 0 up to
                and including history.entry_count

        Returns:
            An immutable cursor describing the given position

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCursorError:
                If the history is None, position is negative, or
                position exceeds history.entry_count
        """

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCursorError(
                    "Cannot build a history cursor for a None "
                    "history."
                )
            )

        if position < 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCursorError(
                    "Cannot build a history cursor: position must "
                    f"not be negative ({position!r})."
                )
            )

        if position > history.entry_count:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCursorError(
                    "Cannot build a history cursor: position "
                    f"({position!r}) must not exceed "
                    "history.entry_count "
                    f"({history.entry_count!r})."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCursor(
                position=position,

                remaining_entries=(
                    history.entry_count
                    - position
                ),

                has_next=(
                    position
                    < history.entry_count
                ),
            )
        )
