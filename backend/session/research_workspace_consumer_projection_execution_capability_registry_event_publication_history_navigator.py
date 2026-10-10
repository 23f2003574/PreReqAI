from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history_cursor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history_navigator_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryNavigatorError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryNavigator:
    """
    Moves a history cursor through a consumer projection execution
    capability registry event publication history.

    The navigator owns cursor movement only. It does NOT read
    sessions, replay history, modify history, filter sessions,
    persist state, or log. Cursor construction and its validation
    are delegated entirely to the injected cursor builder.

    The navigator is:
    - Stateless: Holds only the cursor builder it was given
    - Deterministic: Same history and cursor always produce the
      same result
    - Side-effect free: Never mutates its inputs
    """

    def __init__(

        self,

        cursor_builder,

    ):

        self._cursor_builder = cursor_builder

    def first(

        self,

        history,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor:
        """
        Build a cursor at the beginning of the history.

        Args:
            history: The publication history to navigate

        Returns:
            A cursor at position 0

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryNavigatorError:
                If the history is None
        """

        self._validate_history(
            history
        )

        return self._cursor_builder.build(
            history,

            0,
        )

    def last(

        self,

        history,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor:
        """
        Build a cursor at the end of the history.

        Args:
            history: The publication history to navigate

        Returns:
            A cursor at the last valid session position, or
            position 0 when the history is empty

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryNavigatorError:
                If the history is None
        """

        self._validate_history(
            history
        )

        if history.session_count == 0:

            position = 0

        else:

            position = (
                history.session_count
                - 1
            )

        return self._cursor_builder.build(
            history,

            position,
        )

    def next(

        self,

        history,

        cursor,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor:
        """
        Advance a cursor to the next position within the history.

        Args:
            history: The publication history to navigate
            cursor: The current cursor

        Returns:
            The same cursor when it has no next session, otherwise
            a new cursor advanced by one position

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryNavigatorError:
                If the history or cursor is None
        """

        self._validate_history(
            history
        )

        self._validate_cursor(
            cursor
        )

        if not cursor.has_next:

            return cursor

        position = min(
            cursor.position + 1,

            history.session_count,
        )

        return self._cursor_builder.build(
            history,

            position,
        )

    def previous(

        self,

        history,

        cursor,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor:
        """
        Move a cursor to the previous position within the history.

        Args:
            history: The publication history to navigate
            cursor: The current cursor

        Returns:
            The same cursor when it is already at position 0,
            otherwise a new cursor moved back by one position

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryNavigatorError:
                If the history or cursor is None
        """

        self._validate_history(
            history
        )

        self._validate_cursor(
            cursor
        )

        if cursor.position == 0:

            return cursor

        return self._cursor_builder.build(
            history,

            cursor.position - 1,
        )

    def _validate_history(

        self,

        history,

    ) -> None:

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryNavigatorError(
                    "Cannot navigate a None history."
                )
            )

        if not isinstance(

            history,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryNavigatorError(
                    "Cannot navigate history: history must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory."
                )
            )

    def _validate_cursor(

        self,

        cursor,

    ) -> None:

        if cursor is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryNavigatorError(
                    "Cannot navigate history with a None cursor."
                )
            )

        if not isinstance(

            cursor,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryNavigatorError(
                    "Cannot navigate history: cursor must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor."
                )
            )
