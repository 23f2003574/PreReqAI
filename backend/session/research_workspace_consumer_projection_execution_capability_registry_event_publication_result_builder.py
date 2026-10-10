from .research_workspace_consumer_projection_execution_capability_registry_event_dispatch_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_result_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder:
    """
    Builds an immutable publication result summarizing the outcome
    of a completed consumer projection execution capability registry
    event publication.

    The builder's responsibility is validation and composition, not
    publication or dispatch. It does NOT publish events, dispatch
    events, retry delivery, store subscribers, or perform logging.
    It reuses the existing immutable dispatch result rather than
    recomputing anything.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same result
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        event,

        resolved_subscriber_count,

        dispatch_result,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResult:
        """
        Build a publication result from a publisher's event, its
        resolved subscriber count, and the dispatch result produced
        for it.

        Args:
            event: The event that was published
            resolved_subscriber_count: The number of subscribers
                resolved for the event
            dispatch_result: The dispatch result produced for the
                event

        Returns:
            An immutable publication result, with `published` true
            exactly when the dispatch result reports completion

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultError:
                If the event or dispatch result is None, the
                subscriber count is negative, the dispatch result's
                event does not match the given event, or the
                dispatch result's subscriber count does not match
                resolved_subscriber_count
        """

        if event is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultError(
                    "Cannot build a publication result for a None "
                    "event."
                )
            )

        if dispatch_result is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultError(
                    "Cannot build a publication result from a "
                    "None dispatch result."
                )
            )

        if not isinstance(

            dispatch_result,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResult,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultError(
                    "Cannot build a publication result: "
                    "dispatch_result must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResult."
                )
            )

        if resolved_subscriber_count < 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultError(
                    "Cannot build a publication result: "
                    "resolved_subscriber_count must not be "
                    f"negative ({resolved_subscriber_count!r})."
                )
            )

        if dispatch_result.event != event:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultError(
                    "Cannot build a publication result: "
                    "dispatch_result.event does not match the "
                    "published event."
                )
            )

        if (

            dispatch_result.subscriber_count
            != resolved_subscriber_count
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultError(
                    "Cannot build a publication result: "
                    "dispatch_result.subscriber_count "
                    f"({dispatch_result.subscriber_count!r}) does "
                    "not match resolved_subscriber_count "
                    f"({resolved_subscriber_count!r})."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResult(
                event=event,

                resolved_subscriber_count=resolved_subscriber_count,

                dispatch_result=dispatch_result,

                published=dispatch_result.completed,
            )
        )
