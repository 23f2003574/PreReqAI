from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolver_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolverError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolver:
    """
    Resolves the active, publication-ready subscriptions held by a
    consumer projection execution capability registry event
    subscription registry.

    The resolver performs subscription resolution only - it does
    NOT dispatch events, invoke subscribers, mutate subscriptions,
    activate or deactivate subscriptions, persist state, retry
    failures, or filter beyond active status. The current
    resolution policy simply returns every active subscription;
    future filtering strategies can be introduced behind this
    abstraction without changing publishers.

    The resolver is:
    - Stateless: No instance state
    - Deterministic: Same registry and event always produce the
      same resolved subscriptions
    - Side-effect free: Never mutates the registry or event
    - Thread-safe: No shared mutable state; relies on the registry's
      own thread-safe snapshot
    """

    def resolve(

        self,

        registry,

        event,

    ) -> tuple:
        """
        Resolve the active subscriptions currently registered, in
        registration order.

        Args:
            registry: The subscription registry to resolve against
            event: The event publication is being resolved for. The
                event's payload is never inspected by this resolver

        Returns:
            An immutable tuple of the registry's active
            subscriptions, in registration order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolverError:
                If the registry is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry,
                or the event is None
        """

        if registry is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolverError(
                    "Cannot resolve subscriptions for a None "
                    "registry."
                )
            )

        if not isinstance(

            registry,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolverError(
                    "Cannot resolve subscriptions: registry must "
                    "be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry."
                )
            )

        if event is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolverError(
                    "Cannot resolve subscriptions for a None "
                    "event."
                )
            )

        return tuple(

            subscription

            for subscription

            in registry.subscriptions()

            if subscription.active
        )
