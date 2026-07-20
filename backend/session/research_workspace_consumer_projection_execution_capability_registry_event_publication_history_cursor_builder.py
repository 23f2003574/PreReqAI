from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history_cursor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history_cursor_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder:
    """
    Builds an immutable cursor representing a position within a
    consumer projection execution capability registry event
    publication history.

    The builder's responsibility is validation and computation of
    traversal state, not navigation. It does NOT navigate history,
    replay sessions, modify history, or inspect individual
    publication sessions - only history.session_count is consulted.

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

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor:
        """
        Build a cursor for a position within a publication history.

        Args:
            history: The publication history to build a cursor
                against
            position: The position within the history, from 0 up to
                and including history.session_count

        Returns:
            An immutable cursor describing the given position

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorError:
                If the history is None, position is negative, or
                position exceeds history.session_count
        """

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorError(
                    "Cannot build a history cursor for a None "
                    "history."
                )
            )

        if not isinstance(

            history,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorError(
                    "Cannot build a history cursor: history must "
                    "be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory."
                )
            )

        if position < 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorError(
                    "Cannot build a history cursor: position must "
                    f"not be negative ({position!r})."
                )
            )

        if position > history.session_count:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorError(
                    "Cannot build a history cursor: position "
                    f"({position!r}) must not exceed "
                    "history.session_count "
                    f"({history.session_count!r})."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor(
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
