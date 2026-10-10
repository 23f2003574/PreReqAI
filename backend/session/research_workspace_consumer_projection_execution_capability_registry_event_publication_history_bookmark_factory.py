from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history_bookmark import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmark,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history_bookmark_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_history_cursor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkFactory:
    """
    Creates and restores immutable bookmarks capturing a saved
    traversal position within a consumer projection execution
    capability registry event publication history.

    The factory owns bookmark capture and restoration only. It does
    NOT navigate history, read sessions, replay history, modify
    history, persist bookmarks, or log. Cursor construction on
    restore is delegated entirely to the injected cursor builder.

    The factory is:
    - Stateless: Holds only the cursor builder it was given
    - Deterministic: Same inputs always produce the same bookmark
      or cursor
    - Side-effect free: Never mutates its inputs
    """

    def __init__(

        self,

        cursor_builder,

    ):

        self._cursor_builder = cursor_builder

    def create(

        self,

        history,

        cursor,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmark:
        """
        Capture the current traversal position as an immutable
        bookmark.

        Args:
            history: The publication history being traversed
            cursor: The cursor whose position should be bookmarked

        Returns:
            An immutable bookmark capturing the cursor's position
            and the history's current session count

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkError:
                If the history or cursor is None
        """

        self._validate_history(
            history
        )

        self._validate_cursor(
            cursor
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmark(
                position=cursor.position,

                session_count=history.session_count,
            )
        )

    def restore(

        self,

        bookmark,

        history,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor:
        """
        Rebuild a cursor from a previously created bookmark.

        Args:
            bookmark: The bookmark to restore
            history: The publication history to restore the cursor
                against

        Returns:
            A cursor at the bookmarked position, built by the
            injected cursor builder

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkError:
                If the bookmark or history is None, or the
                bookmark's session_count does not match
                history.session_count
        """

        if bookmark is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkError(
                    "Cannot restore a None bookmark."
                )
            )

        if not isinstance(

            bookmark,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmark,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkError(
                    "Cannot restore bookmark: bookmark must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmark."
                )
            )

        self._validate_history(
            history
        )

        if bookmark.session_count != history.session_count:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkError(
                    "Cannot restore bookmark: bookmark.session_count "
                    f"({bookmark.session_count!r}) does not match "
                    "history.session_count "
                    f"({history.session_count!r})."
                )
            )

        return self._cursor_builder.build(
            history,

            bookmark.position,
        )

    def _validate_history(

        self,

        history,

    ) -> None:

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkError(
                    "Cannot use a None history."
                )
            )

        if not isinstance(

            history,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkError(
                    "Cannot use history: history must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory."
                )
            )

    def _validate_cursor(

        self,

        cursor,

    ) -> None:

        if cursor is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkError(
                    "Cannot create a bookmark from a None cursor."
                )
            )

        if not isinstance(

            cursor,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkError(
                    "Cannot create a bookmark: cursor must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor."
                )
            )
