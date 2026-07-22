from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_entry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntry,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBuilder:
    """
    Builds an immutable, chronological history of consumer
    projection execution capability registry event subscription
    lifecycle transition execution history entries.

    The builder's responsibility is validation and aggregation, not
    replay or navigation. It does NOT replay transitions, navigate
    entries, search entries, filter entries, persist history,
    generate sequence numbers, execute transitions, or log - it
    reuses the entries it is given as-is, in the order supplied.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same entries always produce the same history
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        entries,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistory:
        """
        Build an execution history from a chronological collection
        of history entries.

        Args:
            entries: The history entries, in chronological order.
                May be empty. Sequence numbers must be strictly
                increasing.

        Returns:
            An immutable execution history preserving the exact
            order of the given entries

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryError:
                If the entry collection is None, any entry within it
                is None or not a history entry, or sequence numbers
                are not strictly increasing
        """

        if entries is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryError(
                    "Cannot build an execution history from a "
                    "None entry collection."
                )
            )

        ordered_entries = tuple(
            entries
        )

        for entry in ordered_entries:

            if entry is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryError(
                        "Cannot build an execution history: the "
                        "entry collection contains a None entry."
                    )
                )

            if not isinstance(

                entry,

                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntry,
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryError(
                        "Cannot build an execution history: every "
                        "entry must be a "
                        "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntry."
                    )
                )

        for previous_entry, next_entry in zip(

            ordered_entries,

            ordered_entries[1:],
        ):

            if next_entry.sequence_number <= previous_entry.sequence_number:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryError(
                        "Cannot build an execution history: "
                        "sequence numbers must be strictly "
                        f"increasing (found {previous_entry.sequence_number!r} "
                        f"followed by {next_entry.sequence_number!r})."
                    )
                )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistory(
                entries=ordered_entries,

                entry_count=len(
                    ordered_entries
                ),
            )
        )
