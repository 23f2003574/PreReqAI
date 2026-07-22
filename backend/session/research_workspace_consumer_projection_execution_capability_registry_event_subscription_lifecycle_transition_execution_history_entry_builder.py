from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_entry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntry,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_entry_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder:
    """
    Builds an immutable history entry recording one completed
    consumer projection execution capability registry event
    subscription lifecycle transition execution at a given sequence
    position.

    The builder's responsibility is validation and capture, not
    history management. It does NOT replay transitions, execute
    transitions, validate transitions, persist history, generate
    sequence numbers, publish events, log, or compute metrics.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same sequence number and execution result
      always produce the same entry
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        sequence_number,

        execution_result,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntry:
        """
        Build a history entry recording an execution result at a
        given sequence number.

        Args:
            sequence_number: The entry's position within its
                history; must be zero or positive
            execution_result: The execution result this entry
                records

        Returns:
            An immutable history entry

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryError:
                If sequence_number is None or negative, or
                execution_result is None or the wrong type
        """

        if sequence_number is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryError(
                    "Cannot build a history entry with a None "
                    "sequence_number."
                )
            )

        if sequence_number < 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryError(
                    "Cannot build a history entry: sequence_number "
                    f"({sequence_number!r}) must not be negative."
                )
            )

        if execution_result is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryError(
                    "Cannot build a history entry for a None "
                    "execution_result."
                )
            )

        if not isinstance(

            execution_result,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResult,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryError(
                    "Cannot build a history entry: execution_result "
                    "must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResult."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntry(
                sequence_number=sequence_number,

                execution_result=execution_result,
            )
        )
