from .research_workspace_consumer_projection_execution_capability_registry_event_subscriber import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder:
    """
    Builds an immutable subscription capturing a subscriber's
    registration within the consumer projection execution capability
    registry.

    The builder's responsibility is validation and capture of
    registration metadata, not registration itself. It does NOT
    register subscribers, unregister subscribers, dispatch events,
    publish events, or track delivery state.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same subscription
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        subscriber,

        subscription_id: str,

        active: bool = True,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription:
        """
        Build a subscription capturing a subscriber's registration.

        Args:
            subscriber: The subscriber being registered
            subscription_id: The identifier assigned to this
                registration
            active: Whether the subscription is currently active

        Returns:
            An immutable subscription

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionError:
                If the subscriber is None or not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
                or the subscription ID is None, empty, or blank
        """

        if subscriber is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionError(
                    "Cannot build a subscription for a None subscriber."
                )
            )

        if not isinstance(

            subscriber,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionError(
                    "Cannot build a subscription: subscriber must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber."
                )
            )

        if subscription_id is None or not subscription_id.strip():

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionError(
                    "Cannot build a subscription with an empty or "
                    "blank subscription ID."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription(
                subscriber=subscriber,

                subscription_id=subscription_id,

                active=active,
            )
        )
