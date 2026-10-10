from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_window import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindow,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_window_session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSession,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_window_session_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionBuilder:
    """
    Builds an immutable window session aggregating a consumer
    projection execution capability registry event subscription
    resolution history with its active traversal window.

    The builder's responsibility is validation and aggregation, not
    navigation. It does NOT navigate history, replay sessions,
    modify history, filter windows, persist sessions, or process
    resolution sessions - it reuses the given window as-is.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same session
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        history,

        current_window,

        window_size,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSession:
        """
        Build a window session from a history, its current window,
        and the window size it was built with.

        Args:
            history: The resolution history being traversed
            current_window: The active window within the history
            window_size: The window size the session is built with

        Returns:
            An immutable window session, with has_remaining_windows
            mirrored from current_window.has_more

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionError:
                If the history or current window is None,
                window_size is not greater than zero, or
                current_window.window_size does not match
                window_size
        """

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionError(
                    "Cannot build a window session for a None "
                    "history."
                )
            )

        if not isinstance(

            history,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionError(
                    "Cannot build a window session: history must "
                    "be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory."
                )
            )

        if current_window is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionError(
                    "Cannot build a window session with a None "
                    "current window."
                )
            )

        if not isinstance(

            current_window,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindow,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionError(
                    "Cannot build a window session: current_window "
                    "must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindow."
                )
            )

        if window_size <= 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionError(
                    "Cannot build a window session: window_size "
                    f"must be greater than zero ({window_size!r})."
                )
            )

        if current_window.window_size != window_size:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionError(
                    "Cannot build a window session: "
                    "current_window.window_size "
                    f"({current_window.window_size!r}) does not "
                    f"match window_size ({window_size!r})."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSession(
                history=history,

                current_window=current_window,

                window_size=window_size,

                has_remaining_windows=(
                    current_window.has_more
                ),
            )
        )
