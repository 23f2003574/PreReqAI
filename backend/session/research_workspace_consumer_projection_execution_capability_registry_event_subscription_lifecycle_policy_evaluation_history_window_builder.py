from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_history_window import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryWindow,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_history_window_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryWindowError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryWindowBuilder:
    """
    Builds an immutable, fixed-size contiguous window over a
    consumer projection execution capability registry event
    subscription lifecycle policy evaluation history.

    The builder's responsibility is validation and slicing, not
    navigation or replay. It does NOT navigate history, replay
    evaluations, filter entries, modify history, evaluate policies,
    persist windows, log, compute metrics, or inspect individual
    entry contents beyond the slice itself.

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

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryWindow:
        """
        Build a fixed-size window over an evaluation history.

        Args:
            history: The evaluation history to window
            start_position: The position the window begins at, from
                0 up to and including history.entry_count
            window_size: The requested window size, must be greater
                than zero

        Returns:
            An immutable window preserving chronological entry
            ordering, with has_more set when entries remain beyond
            the end of this window

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryWindowError:
                If the history is None, start_position is negative
                or exceeds history.entry_count, or window_size is
                not greater than zero
        """

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryWindowError(
                    "Cannot build a history window for a None "
                    "history."
                )
            )

        if start_position < 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryWindowError(
                    "Cannot build a history window: start_position "
                    f"must not be negative ({start_position!r})."
                )
            )

        if start_position > history.entry_count:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryWindowError(
                    "Cannot build a history window: start_position "
                    f"({start_position!r}) must not exceed "
                    "history.entry_count "
                    f"({history.entry_count!r})."
                )
            )

        if window_size <= 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryWindowError(
                    "Cannot build a history window: window_size "
                    f"must be greater than zero ({window_size!r})."
                )
            )

        end_position = min(

            start_position + window_size,

            history.entry_count,
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryWindow(
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
