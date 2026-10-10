from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_cursor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursor,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_cursor_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursorError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursorBuilder:
    """
    Builds an immutable cursor representing a position within a
    consumer projection execution capability registry event
    subscription resolution history.

    The builder's responsibility is validation and computation of
    traversal state, not navigation. It does NOT navigate history,
    replay sessions, modify history, or inspect individual
    resolution sessions - only history.session_count is consulted.

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

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursor:
        """
        Build a cursor for a position within a resolution history.

        Args:
            history: The resolution history to build a cursor
                against
            position: The position within the history, from 0 up to
                and including history.session_count

        Returns:
            An immutable cursor describing the given position

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursorError:
                If the history is None, position is negative, or
                position exceeds history.session_count
        """

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursorError(
                    "Cannot build a history cursor for a None "
                    "history."
                )
            )

        if not isinstance(

            history,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursorError(
                    "Cannot build a history cursor: history must "
                    "be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory."
                )
            )

        if position < 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursorError(
                    "Cannot build a history cursor: position must "
                    f"not be negative ({position!r})."
                )
            )

        if position > history.session_count:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursorError(
                    "Cannot build a history cursor: position "
                    f"({position!r}) must not exceed "
                    "history.session_count "
                    f"({history.session_count!r})."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursor(
                position=position,

                remaining_sessions=(
                    history.session_count
                    - position
                ),

                has_next=(
                    position
                    < history.session_count
                ),
            )
        )
