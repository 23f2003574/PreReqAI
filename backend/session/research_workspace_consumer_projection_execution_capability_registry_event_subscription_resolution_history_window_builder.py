from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_window import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindow,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_window_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder:
    """
    Builds an immutable, fixed-size contiguous window over a
    consumer projection execution capability registry event
    subscription resolution history.

    The builder's responsibility is validation and slicing, not
    navigation or replay. It does NOT replay sessions, navigate
    history, filter sessions, modify history, persist windows, or
    inspect individual session contents beyond the slice itself.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same history, start position, and window size
      always produce the same window
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        history,

        start_position,

        window_size,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindow:
        """
        Build a fixed-size window over a resolution history.

        Args:
            history: The resolution history to window
            start_position: The position the window begins at, from
                0 up to and including history.session_count
            window_size: The requested window size, must be greater
                than zero

        Returns:
            An immutable window preserving chronological session
            ordering, with has_more set when sessions remain beyond
            the end of this window

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowError:
                If the history is None, start_position is negative
                or exceeds history.session_count, or window_size is
                not greater than zero
        """

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowError(
                    "Cannot build a history window for a None "
                    "history."
                )
            )

        if not isinstance(

            history,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowError(
                    "Cannot build a history window: history must "
                    "be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory."
                )
            )

        if start_position < 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowError(
                    "Cannot build a history window: start_position "
                    f"must not be negative ({start_position!r})."
                )
            )

        if start_position > history.session_count:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowError(
                    "Cannot build a history window: start_position "
                    f"({start_position!r}) must not exceed "
                    "history.session_count "
                    f"({history.session_count!r})."
                )
            )

        if window_size <= 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowError(
                    "Cannot build a history window: window_size "
                    f"must be greater than zero ({window_size!r})."
                )
            )

        end_position = min(

            start_position + window_size,

            history.session_count,
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindow(
                start_position=start_position,

                window_size=window_size,

                sessions=(
                    history.sessions[
                        start_position:end_position
                    ]
                ),

                has_more=(
                    end_position
                    < history.session_count
                ),
            )
        )
