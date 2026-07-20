from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history_cursor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history_read_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryReadResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history_reader_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryReaderError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryReader:
    """
    Reads a single consumer projection execution capability registry
    event publication session from a publication history at a given
    cursor position.

    The reader performs deterministic access only. It does NOT
    advance the cursor, navigate history, replay sessions, modify
    history, filter sessions, persist state, or log.

    The reader is:
    - Stateless: No instance state
    - Deterministic: Same history and cursor always produce the
      same read result
    - Side-effect free: Never mutates its inputs
    """

    def read(

        self,

        history,

        cursor,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryReadResult:
        """
        Read the session at a cursor's position within a publication
        history, without advancing traversal.

        Args:
            history: The publication history to read from
            cursor: The cursor describing the position to read

        Returns:
            An immutable read result. When the cursor has no next
            session, session is None and reached_end is True.
            Otherwise session is the session at the cursor's
            position and reached_end is False. The cursor is
            returned unchanged either way.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryReaderError:
                If the history or cursor is None, or the cursor's
                position falls outside the history's bounds
        """

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryReaderError(
                    "Cannot read from a None history."
                )
            )

        if not isinstance(

            history,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryReaderError(
                    "Cannot read history: history must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory."
                )
            )

        if cursor is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryReaderError(
                    "Cannot read history with a None cursor."
                )
            )

        if not isinstance(

            cursor,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryReaderError(
                    "Cannot read history: cursor must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor."
                )
            )

        if (

            cursor.position < 0

            or cursor.position > history.session_count
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryReaderError(
                    "Cannot read history: cursor position "
                    f"({cursor.position!r}) is outside history "
                    "bounds "
                    f"(0..{history.session_count!r})."
                )
            )

        if not cursor.has_next:

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryReadResult(
                    session=None,

                    cursor=cursor,

                    reached_end=True,
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryReadResult(
                session=history.sessions[
                    cursor.position
                ],

                cursor=cursor,

                reached_end=False,
            )
        )
