from .research_workspace_consumer_projection_execution_capability_registry_event_dispatch_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_dispatch_result_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder:
    """
    Builds an immutable dispatch result summarizing the outcome of a
    completed consumer projection execution capability registry
    event dispatch.

    The builder's responsibility is validation and composition, not
    dispatching. It does NOT perform dispatch, retry failures, store
    exceptions, or perform logging.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same result
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        event,

        subscriber_count,

        successful_dispatch_count,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResult:
        """
        Build a dispatch result from dispatch outcome counts.

        Args:
            event: The event that was dispatched
            subscriber_count: The number of subscribers dispatch was
                attempted against
            successful_dispatch_count: The number of subscribers
                that were successfully handled

        Returns:
            An immutable dispatch result, with `completed` true
            exactly when successful_dispatch_count equals
            subscriber_count

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultError:
                If the event is None, either count is negative, or
                successful_dispatch_count exceeds subscriber_count
        """

        if event is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultError(
                    "Cannot build a dispatch result for a None "
                    "event."
                )
            )

        if subscriber_count < 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultError(
                    "Cannot build a dispatch result: "
                    "subscriber_count must not be negative "
                    f"({subscriber_count!r})."
                )
            )

        if successful_dispatch_count < 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultError(
                    "Cannot build a dispatch result: "
                    "successful_dispatch_count must not be "
                    f"negative ({successful_dispatch_count!r})."
                )
            )

        if successful_dispatch_count > subscriber_count:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultError(
                    "Cannot build a dispatch result: "
                    "successful_dispatch_count "
                    f"({successful_dispatch_count!r}) must not "
                    "exceed subscriber_count "
                    f"({subscriber_count!r})."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResult(
                event=event,

                subscriber_count=subscriber_count,

                successful_dispatch_count=successful_dispatch_count,

                completed=(
                    successful_dispatch_count
                    == subscriber_count
                ),
            )
        )
