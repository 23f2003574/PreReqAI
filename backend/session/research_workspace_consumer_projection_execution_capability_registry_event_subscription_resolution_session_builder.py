from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolution,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSession,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_session_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionBuilder:
    """
    Builds an immutable resolution session aggregating a consumer
    projection execution capability registry event with its
    completed subscription resolution.

    The builder's responsibility is validation and aggregation, not
    resolution. It does NOT resolve subscriptions, dispatch events,
    publish events, retry operations, or mutate the resolution it is
    given - it reuses it as-is.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same session
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        event,

        resolution,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSession:
        """
        Build a resolution session from an event and its
        subscription resolution.

        Args:
            event: The event resolution was performed for
            resolution: The subscription resolution produced for
                the event

        Returns:
            An immutable resolution session, with
            resolved_subscription_count mirrored from the
            resolution and resolution_completed set to True

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionError:
                If the event or resolution is None, or the
                resolution's event does not match the given event
        """

        if event is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionError(
                    "Cannot build a resolution session for a None "
                    "event."
                )
            )

        if resolution is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionError(
                    "Cannot build a resolution session from a "
                    "None resolution."
                )
            )

        if not isinstance(

            resolution,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolution,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionError(
                    "Cannot build a resolution session: "
                    "resolution must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolution."
                )
            )

        if resolution.event != event:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionError(
                    "Cannot build a resolution session: "
                    "resolution.event does not match the given "
                    "event."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSession(
                event=event,

                resolution=resolution,

                resolved_subscription_count=(
                    resolution.resolved_subscription_count
                ),

                resolution_completed=True,
            )
        )
