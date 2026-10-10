from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_bookmark import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmark,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_bookmark_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmarkError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_cursor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursor,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmarkFactory:
    """
    Creates and restores immutable bookmarks capturing a saved
    traversal position within a consumer projection execution
    capability registry event subscription resolution history.

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

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmark:
        """
        Capture the current traversal position as an immutable
        bookmark.

        Args:
            history: The resolution history being traversed
            cursor: The cursor whose position should be bookmarked

        Returns:
            An immutable bookmark capturing the cursor's position
            and the history's current session count

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmarkError:
                If the history or cursor is None
        """

        self._validate_history(
            history
        )

        self._validate_cursor(
            cursor
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmark(
                position=cursor.position,

                session_count=history.session_count,
            )
        )

    def restore(

        self,

        bookmark,

        history,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursor:
        """
        Rebuild a cursor from a previously created bookmark.

        Args:
            bookmark: The bookmark to restore
            history: The resolution history to restore the cursor
                against

        Returns:
            A cursor at the bookmarked position, built by the
            injected cursor builder

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmarkError:
                If the bookmark or history is None, or the
                bookmark's session_count does not match
                history.session_count
        """

        if bookmark is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmarkError(
                    "Cannot restore a None bookmark."
                )
            )

        if not isinstance(

            bookmark,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmark,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmarkError(
                    "Cannot restore bookmark: bookmark must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmark."
                )
            )

        self._validate_history(
            history
        )

        if bookmark.session_count != history.session_count:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmarkError(
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
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmarkError(
                    "Cannot use a None history."
                )
            )

        if not isinstance(

            history,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmarkError(
                    "Cannot use history: history must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory."
                )
            )

    def _validate_cursor(

        self,

        cursor,

    ) -> None:

        if cursor is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmarkError(
                    "Cannot create a bookmark from a None cursor."
                )
            )

        if not isinstance(

            cursor,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursor,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmarkError(
                    "Cannot create a bookmark: cursor must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursor."
                )
            )
