from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_cursor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursor,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_read_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReadResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_reader_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReaderError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReader:
    """
    Reads a single consumer projection execution capability registry
    event subscription lifecycle transition execution history entry
    from an execution history at a given cursor position.

    The reader performs deterministic access only. It does NOT
    advance the cursor, navigate history, replay transitions, modify
    history, filter entries, persist data, log, or compute metrics.

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

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReadResult:
        """
        Read the entry at a cursor's position within an execution
        history, without advancing traversal.

        Args:
            history: The execution history to read from
            cursor: The cursor describing the position to read

        Returns:
            An immutable read result. When the cursor has no next
            entry, entry is None and entry_found is False.
            Otherwise entry is the entry at the cursor's position
            and entry_found is True. The cursor is returned
            unchanged either way.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReaderError:
                If the history or cursor is None, or the cursor's
                position falls outside the history's bounds
        """

        if history is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReaderError(
                    "Cannot read from a None history."
                )
            )

        if not isinstance(

            history,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistory,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReaderError(
                    "Cannot read history: history must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistory."
                )
            )

        if cursor is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReaderError(
                    "Cannot read history with a None cursor."
                )
            )

        if not isinstance(

            cursor,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursor,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReaderError(
                    "Cannot read history: cursor must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursor."
                )
            )

        if (

            cursor.position < 0

            or cursor.position > history.entry_count
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReaderError(
                    "Cannot read history: cursor position "
                    f"({cursor.position!r}) is outside history "
                    "bounds "
                    f"(0..{history.entry_count!r})."
                )
            )

        if not cursor.has_next:

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReadResult(
                    cursor=cursor,

                    entry=None,

                    entry_found=False,
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReadResult(
                cursor=cursor,

                entry=history.entries[
                    cursor.position
                ],

                entry_found=True,
            )
        )
