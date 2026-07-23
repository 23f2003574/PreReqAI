from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_history_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryBuilder:
    """
    Builds an immutable, chronological history of consumer
    projection execution capability registry event subscription
    lifecycle policy evaluation history entries.

    The builder's responsibility is validation and aggregation, not
    replay or navigation. It does NOT evaluate policies, replay
    evaluations, navigate entries, search entries, filter entries,
    persist history, generate sequence numbers, or log - it reuses
    the entries it is given as-is, in the order supplied.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same entries always produce the same history
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        entries,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistory:
        """
        Build an evaluation history from a chronological collection
        of history entries.

        Args:
            entries: The history entries, in chronological order.
                May be empty. Sequence numbers must be strictly
                increasing.

        Returns:
            An immutable evaluation history preserving the exact
            order of the given entries

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryError:
                If the entry collection is None, any entry within it
                is None, or sequence numbers are not strictly
                increasing
        """

        if entries is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryError(
                    "Cannot build an evaluation history from a "
                    "None entry collection."
                )
            )

        ordered_entries = tuple(
            entries
        )

        for entry in ordered_entries:

            if entry is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryError(
                        "Cannot build an evaluation history: the "
                        "entry collection contains a None entry."
                    )
                )

        for previous_entry, next_entry in zip(

            ordered_entries,

            ordered_entries[1:],
        ):

            if next_entry.sequence_number <= previous_entry.sequence_number:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryError(
                        "Cannot build an evaluation history: "
                        "sequence numbers must be strictly "
                        f"increasing (found {previous_entry.sequence_number!r} "
                        f"followed by {next_entry.sequence_number!r})."
                    )
                )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistory(
                entries=ordered_entries,

                entry_count=len(
                    ordered_entries
                ),
            )
        )
