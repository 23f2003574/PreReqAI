from .research_workspace_consumer_projection_execution_capability_registry_event_dispatcher_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcherError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcher:
    """
    Delivers a consumer projection execution capability registry
    event to its resolved subscribers, in order.

    The dispatcher owns delivery only - it does NOT discover
    subscribers, register subscribers, publish events, filter
    subscribers, transform events, persist anything, or retry.
    Those responsibilities belong elsewhere in the pipeline.

    Each subscriber is invoked exactly once, in the order given, via
    `subscriber.handle(event)`. If a subscriber raises, dispatch
    stops immediately and the exception propagates unchanged - no
    later subscriber is invoked.

    The dispatcher is:
    - Stateless: No instance state
    - Deterministic: Same event and subscribers always produce the
      same sequence of handle() calls
    - Side-effect free: Never mutates its inputs, only delegates
    - Thread-safe: No shared mutable state
    """

    def dispatch(

        self,

        event,

        subscribers,

    ) -> None:
        """
        Deliver an event to each subscriber, in order.

        Args:
            event: The event to deliver
            subscribers: The subscribers to deliver the event to, in
                the order they should be invoked

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcherError:
                If the event is None, the subscriber collection is
                None, or any subscriber within it is None
        """

        if event is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcherError(
                    "Cannot dispatch a None event."
                )
            )

        if subscribers is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcherError(
                    "Cannot dispatch to a None subscriber "
                    "collection."
                )
            )

        for subscriber in subscribers:

            if subscriber is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcherError(
                        "Cannot dispatch to a None subscriber."
                    )
                )

        for subscriber in subscribers:

            subscriber.handle(
                event
            )

        return None
