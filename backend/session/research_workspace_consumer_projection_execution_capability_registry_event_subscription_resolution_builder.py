from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolution,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder:
    """
    Builds an immutable resolution capturing the subscriptions
    selected for publication of a consumer projection execution
    capability registry event.

    The builder's responsibility is validation and capture of
    resolution metadata, not resolution itself. It does NOT dispatch
    events, invoke subscribers, register subscriptions, activate or
    deactivate subscriptions, mutate subscriptions, or persist state.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same event and subscriptions always produce the
      same resolution
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        event,

        subscriptions,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolution:
        """
        Build a resolution capturing an event and the subscriptions
        resolved for it.

        Args:
            event: The event resolution was performed for
            subscriptions: The resolved subscriptions, in resolution
                order

        Returns:
            An immutable resolution

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionError:
                If the event is None, the subscription collection is
                None, or any subscription within it is None
        """

        if event is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionError(
                    "Cannot build a resolution for a None event."
                )
            )

        if subscriptions is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionError(
                    "Cannot build a resolution with a None "
                    "subscription collection."
                )
            )

        for subscription in subscriptions:

            if subscription is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionError(
                        "Cannot build a resolution with a None "
                        "subscription entry."
                    )
                )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolution(
                event=event,

                subscriptions=subscriptions,

                resolved_subscription_count=(
                    len(subscriptions)
                ),
            )
        )
