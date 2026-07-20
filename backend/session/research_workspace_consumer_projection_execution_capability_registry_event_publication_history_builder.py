from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSession,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder:
    """
    Builds an immutable, chronological history of completed consumer
    projection execution capability registry event publication
    sessions.

    The builder's responsibility is validation and aggregation, not
    publication or replay. It does NOT publish events, replay
    history, filter sessions, sort sessions, or mutate the sessions
    it is given - it reuses them as-is, in the order supplied.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same sessions always produce the same history
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        sessions,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory:
        """
        Build a publication history from a chronological collection
        of publication sessions.

        Args:
            sessions: The publication sessions, in chronological
                order. May be empty.

        Returns:
            An immutable publication history preserving the exact
            order of the given sessions

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryError:
                If the session collection is None or any session
                within it is None or not a publication session
        """

        if sessions is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryError(
                    "Cannot build a publication history from a "
                    "None session collection."
                )
            )

        ordered_sessions = tuple(
            sessions
        )

        for session in ordered_sessions:

            if session is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryError(
                        "Cannot build a publication history: the "
                        "session collection contains a None "
                        "session."
                    )
                )

            if not isinstance(

                session,

                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSession,
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryError(
                        "Cannot build a publication history: "
                        "every session must be a "
                        "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSession."
                    )
                )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory(
                sessions=ordered_sessions,

                session_count=len(
                    ordered_sessions
                ),
            )
        )
