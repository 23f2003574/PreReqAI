from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_bookmark import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmark,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_bookmark_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_cursor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursor,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkFactory:
    """
    Creates and restores immutable bookmarks capturing a saved
    traversal position within a consumer projection execution
    capability registry event subscription lifecycle transition
    execution history.

    The factory owns bookmark capture and restoration only. It does
    NOT navigate history, read entries, replay transitions, modify
    history, persist bookmarks, log, or compute metrics. Cursor
    construction on restore is delegated entirely to the injected
    cursor builder.

    The factory is:
    - Stateless: Holds only the cursor builder it was given
    - Deterministic: Same inputs always produce the same bookmark
      or cursor
    - Thread-safe: No shared mutable state
    - Side-effect free: Never mutates its inputs

    Its cursor builder must always be supplied by the caller. The
    factory never instantiates it internally.
    """

    def __init__(

        self,

        cursor_builder,

    ):

        self._cursor_builder = cursor_builder

    def create(

        self,

        cursor,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmark:
        """
        Capture the current traversal position as an immutable
        bookmark.

        Args:
            cursor: The cursor whose position should be bookmarked

        Returns:
            An immutable bookmark capturing the cursor's position

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkError:
                If the cursor is None or the wrong type
        """

        if cursor is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkError(
                    "Cannot create a bookmark from a None cursor."
                )
            )

        if not isinstance(

            cursor,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursor,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkError(
                    "Cannot create a bookmark: cursor must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursor."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmark(
                position=cursor.position,
            )
        )

    def restore(

        self,

        history,

        bookmark,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursor:
        """
        Rebuild a cursor from a previously created bookmark.

        Args:
            history: The execution history to restore the cursor
                against
            bookmark: The bookmark to restore

        Returns:
            A cursor at the bookmarked position, built by the
            injected cursor builder

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkError:
                If the history or bookmark is None or the wrong
                type, or bookmark.position falls outside the
                history's bounds
        """

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkError(
                    "Cannot restore a bookmark against a None "
                    "history."
                )
            )

        if not isinstance(

            history,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistory,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkError(
                    "Cannot restore bookmark: history must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistory."
                )
            )

        if bookmark is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkError(
                    "Cannot restore a None bookmark."
                )
            )

        if not isinstance(

            bookmark,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmark,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkError(
                    "Cannot restore bookmark: bookmark must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmark."
                )
            )

        if (

            bookmark.position < 0

            or bookmark.position > history.entry_count
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkError(
                    "Cannot restore bookmark: bookmark.position "
                    f"({bookmark.position!r}) is outside history "
                    "bounds "
                    f"(0..{history.entry_count!r})."
                )
            )

        return self._cursor_builder.build(
            history,

            bookmark.position,
        )
