from .research_workspace_consumer_projection_execution_capability_registry_event_publication_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSession,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_session_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder:
    """
    Builds an immutable publication session aggregating a consumer
    projection execution capability registry event with its
    completed publication result.

    The builder's responsibility is validation and aggregation, not
    publication. It does NOT publish events, dispatch events,
    resolve subscribers, retry failures, or mutate the publication
    result it is given - it reuses it as-is.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same session
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        event,

        publication_result,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSession:
        """
        Build a publication session from an event and its
        publication result.

        Args:
            event: The event that was published
            publication_result: The publication result produced for
                the event

        Returns:
            An immutable publication session, with subscriber_count
            and publication_completed mirrored from the publication
            result

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionError:
                If the event or publication result is None, or the
                publication result's event does not match the given
                event
        """

        if event is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionError(
                    "Cannot build a publication session for a "
                    "None event."
                )
            )

        if publication_result is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionError(
                    "Cannot build a publication session from a "
                    "None publication result."
                )
            )

        if not isinstance(

            publication_result,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResult,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionError(
                    "Cannot build a publication session: "
                    "publication_result must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResult."
                )
            )

        if publication_result.event != event:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionError(
                    "Cannot build a publication session: "
                    "publication_result.event does not match the "
                    "published event."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSession(
                event=event,

                publication_result=publication_result,

                subscriber_count=publication_result.resolved_subscriber_count,

                publication_completed=publication_result.published,
            )
        )
