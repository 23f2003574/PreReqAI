from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSession,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBuilder:
    """
    Builds an immutable, chronological history of completed consumer
    projection execution capability registry event subscription
    resolution sessions.

    The builder's responsibility is validation and aggregation, not
    resolution or replay. It does NOT resolve subscriptions, dispatch
    events, replay history, filter sessions, sort sessions, or
    mutate the sessions it is given - it reuses them as-is, in the
    order supplied.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same sessions always produce the same history
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        sessions,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory:
        """
        Build a resolution history from a chronological collection
        of resolution sessions.

        Args:
            sessions: The resolution sessions, in chronological
                order. May be empty.

        Returns:
            An immutable resolution history preserving the exact
            order of the given sessions

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryError:
                If the session collection is None or any session
                within it is None or not a resolution session
        """

        if sessions is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryError(
                    "Cannot build a resolution history from a "
                    "None session collection."
                )
            )

        ordered_sessions = tuple(
            sessions
        )

        for session in ordered_sessions:

            if session is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryError(
                        "Cannot build a resolution history: the "
                        "session collection contains a None "
                        "session."
                    )
                )

            if not isinstance(

                session,

                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSession,
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryError(
                        "Cannot build a resolution history: "
                        "every session must be a "
                        "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSession."
                    )
                )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory(
                sessions=ordered_sessions,

                session_count=len(
                    ordered_sessions
                ),
            )
        )
