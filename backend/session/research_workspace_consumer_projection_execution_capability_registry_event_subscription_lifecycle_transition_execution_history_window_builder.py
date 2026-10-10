from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_window import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindow,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_window_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowBuilder:
    """
    Builds an immutable, fixed-size contiguous window over a
    consumer projection execution capability registry event
    subscription lifecycle transition execution history.

    The builder's responsibility is validation and slicing, not
    navigation or replay. It does NOT navigate history, replay
    transitions, filter entries, modify history, persist windows,
    log, compute metrics, or inspect individual entry contents
    beyond the slice itself.

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

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindow:
        """
        Build a fixed-size window over an execution history.

        Args:
            history: The execution history to window
            start_position: The position the window begins at, from
                0 up to and including history.entry_count
            window_size: The requested window size, must be greater
                than zero

        Returns:
            An immutable window preserving chronological entry
            ordering, with has_more set when entries remain beyond
            the end of this window

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowError:
                If the history is None, start_position is negative
                or exceeds history.entry_count, or window_size is
                not greater than zero
        """

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowError(
                    "Cannot build a history window for a None "
                    "history."
                )
            )

        if not isinstance(

            history,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistory,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowError(
                    "Cannot build a history window: history must "
                    "be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistory."
                )
            )

        if start_position < 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowError(
                    "Cannot build a history window: start_position "
                    f"must not be negative ({start_position!r})."
                )
            )

        if start_position > history.entry_count:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowError(
                    "Cannot build a history window: start_position "
                    f"({start_position!r}) must not exceed "
                    "history.entry_count "
                    f"({history.entry_count!r})."
                )
            )

        if window_size <= 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowError(
                    "Cannot build a history window: window_size "
                    f"must be greater than zero ({window_size!r})."
                )
            )

        end_position = min(

            start_position + window_size,

            history.entry_count,
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindow(
                start_position=start_position,

                window_size=window_size,

                entries=(
                    history.entries[
                        start_position:end_position
                    ]
                ),

                has_more=(
                    end_position
                    < history.entry_count
                ),
            )
        )
