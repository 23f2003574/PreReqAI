from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_registry_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistryError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry:
    """
    Maintains the authoritative, immutable set of consumer
    projection execution capability registry event subscriptions.

    Unlike a subscriber registry, this registry manages
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription
    objects rather than raw subscribers. It owns registration
    bookkeeping only - it does NOT dispatch events, publish events,
    activate or deactivate subscriptions, invoke subscribers, retry
    delivery, or persist state.

    The registry is:
    - Deterministic: The same sequence of operations always
      produces the same observable state
    - Thread-safe: All mutation and reads are guarded by an
      internal lock
    - Duplicate-free: No two registered subscriptions may share a
      subscription ID
    """

    def __init__(self):

        self._subscriptions = []

        self._lock = RLock()

    def register(

        self,

        subscription,

    ) -> None:
        """
        Register a subscription.

        Args:
            subscription: The subscription to register

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistryError:
                If the subscription is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription,
                has an empty or blank subscription ID, or its
                subscription ID is already registered
        """

        if subscription is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistryError(
                    "Cannot register a None subscription."
                )
            )

        if not isinstance(

            subscription,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistryError(
                    "Cannot register a subscription: subscription "
                    "must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription."
                )
            )

        if (

            subscription.subscription_id is None

            or not subscription.subscription_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistryError(
                    "Cannot register a subscription with an empty "
                    "or blank subscription ID."
                )
            )

        with self._lock:

            if any(

                existing.subscription_id

                == subscription.subscription_id

                for existing

                in self._subscriptions
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistryError(
                        "Cannot register a subscription: "
                        "subscription ID "
                        f"{subscription.subscription_id!r} is "
                        "already registered."
                    )
                )

            self._subscriptions.append(
                subscription
            )

    def unregister(

        self,

        subscription_id: str,

    ) -> None:
        """
        Remove the subscription matching a subscription ID.

        This is a no-op if no subscription with that ID is
        registered.

        Args:
            subscription_id: The subscription ID to remove
        """

        with self._lock:

            self._subscriptions = [

                existing

                for existing

                in self._subscriptions

                if existing.subscription_id != subscription_id
            ]

    def subscriptions(

        self,

    ) -> tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription,
        ...,
    ]:
        """
        Return an immutable snapshot of all registered subscriptions
        in registration order.
        """

        with self._lock:

            return tuple(
                self._subscriptions
            )

    def find(

        self,

        subscription_id: str,

    ):
        """
        Find the subscription matching a subscription ID.

        Args:
            subscription_id: The subscription ID to look up

        Returns:
            The matching subscription, or None if no subscription
            with that ID is registered
        """

        with self._lock:

            for existing in self._subscriptions:

                if existing.subscription_id == subscription_id:

                    return existing

            return None
