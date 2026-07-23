from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_history_navigator_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryNavigatorError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryNavigator:
    """
    Moves a history cursor through a consumer projection execution
    capability registry event subscription lifecycle policy
    evaluation history.

    The navigator owns cursor movement only. It does NOT read
    history entries, replay evaluations, modify history, filter
    history, persist navigation state, log, or compute metrics.
    Cursor construction and its validation are delegated entirely to
    the injected cursor builder.

    The navigator is:
    - Stateless: Holds only the cursor builder it was given
    - Deterministic: Same history and cursor always produce the
      same result
    - Thread-safe: No shared mutable state
    - Side-effect free: Never mutates its inputs

    Its cursor builder must always be supplied by the caller. The
    navigator never instantiates it internally.
    """

    def __init__(

        self,

        cursor_builder,

    ):

        self._cursor_builder = cursor_builder

    def first(

        self,

        history,

    ):
        """
        Build a cursor at the beginning of the history.

        Args:
            history: The evaluation history to navigate

        Returns:
            A cursor at position 0

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryNavigatorError:
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

    ):
        """
        Build a cursor at the end of the history.

        Args:
            history: The evaluation history to navigate

        Returns:
            A cursor at the last valid entry position, or position
            0 when the history is empty

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryNavigatorError:
                If the history is None
        """

        self._validate_history(
            history
        )

        if history.entry_count == 0:

            position = 0

        else:

            position = (
                history.entry_count
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

    ):
        """
        Advance a cursor to the next position within the history.

        Args:
            history: The evaluation history to navigate
            cursor: The current cursor

        Returns:
            The same cursor when it has no next entry, otherwise a
            new cursor advanced by one position

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryNavigatorError:
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

            history.entry_count,
        )

        return self._cursor_builder.build(
            history,

            position,
        )

    def previous(

        self,

        history,

        cursor,

    ):
        """
        Move a cursor to the previous position within the history.

        Args:
            history: The evaluation history to navigate
            cursor: The current cursor

        Returns:
            The same cursor when it is already at position 0,
            otherwise a new cursor moved back by one position

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryNavigatorError:
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

            max(
                cursor.position - 1,

                0,
            ),
        )

    def _validate_history(

        self,

        history,

    ) -> None:

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryNavigatorError(
                    "Cannot navigate a None history."
                )
            )

    def _validate_cursor(

        self,

        cursor,

    ) -> None:

        if cursor is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryNavigatorError(
                    "Cannot navigate history with a None cursor."
                )
            )
