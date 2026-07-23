from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_history_entry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntry,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_history_entry_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder:
    """
    Builds an immutable history entry recording one completed
    consumer projection execution capability registry event
    subscription lifecycle policy evaluation at a given sequence
    position.

    The builder's responsibility is validation and capture, not
    history management. It does NOT evaluate policies, validate
    transitions, execute lifecycle transitions, replay evaluations,
    persist history, generate sequence numbers, log, or compute
    metrics.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same sequence number and evaluation result
      always produce the same entry
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        sequence_number,

        evaluation_result,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntry:
        """
        Build a history entry recording an evaluation result at a
        given sequence number.

        Args:
            sequence_number: The entry's position within its
                history; must be zero or positive
            evaluation_result: The evaluation result this entry
                records

        Returns:
            An immutable history entry

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryError:
                If sequence_number is None or negative, or
                evaluation_result is None
        """

        if sequence_number is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryError(
                    "Cannot build a history entry with a None "
                    "sequence_number."
                )
            )

        if sequence_number < 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryError(
                    "Cannot build a history entry: sequence_number "
                    f"({sequence_number!r}) must not be negative."
                )
            )

        if evaluation_result is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryError(
                    "Cannot build a history entry for a None "
                    "evaluation_result."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntry(
                sequence_number=sequence_number,

                evaluation_result=evaluation_result,
            )
        )
