from .research_workspace_consumer_projection_execution_capability_registry_event_publisher_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisherError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisher:
    """
    Coordinates publication of consumer projection execution
    capability registry events to their subscribers.

    The publisher owns dispatch orchestration only - it does NOT
    create events, transform events, filter subscribers, retry
    dispatches, persist state, or maintain queues. Those
    responsibilities belong to the injected subscriber registry and
    dispatcher.

    For each event, the publisher asks the subscriber registry to
    resolve subscribers via `resolve(event)`, then hands the event
    and resolved subscribers to the dispatcher via
    `dispatch(event, subscribers)`. A batch is expected to expose
    its events, in publication order, as `batch.events`.

    The publisher is:
    - Stateless: Holds only the two collaborators it was given
    - Deterministic: Same event or batch always produces the same
      sequence of collaborator calls
    - Side-effect free: Never mutates its inputs, only delegates
    - Thread-safe: No shared mutable state
    """

    def __init__(

        self,

        subscriber_registry,

        dispatcher,

    ):

        self._subscriber_registry = subscriber_registry

        self._dispatcher = dispatcher

    def publish(

        self,

        event,

    ) -> None:
        """
        Validate, resolve, and dispatch a single event.

        Args:
            event: The event to publish

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisherError:
                If the event is None
        """

        if event is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisherError(
                    "Cannot publish a None event."
                )
            )

        self._publish_one(
            event
        )

        return None

    def publish_batch(

        self,

        batch,

    ) -> None:
        """
        Validate and publish every event in a batch, in order.

        Args:
            batch: The event batch to publish

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisherError:
                If the batch is None or contains no events
        """

        if batch is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisherError(
                    "Cannot publish a None batch."
                )
            )

        events = (
            batch.events
        )

        if not events:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisherError(
                    "Cannot publish a batch with no events."
                )
            )

        for event in events:

            self._publish_one(
                event
            )

        return None

    def _publish_one(

        self,

        event,

    ) -> None:

        subscribers = (
            self._subscriber_registry.resolve(
                event
            )
        )

        self._dispatcher.dispatch(
            event,

            subscribers,
        )
