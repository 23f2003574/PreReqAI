from abc import (
    ABC,
    abstractmethod,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber(
    ABC
):
    """
    The canonical contract for components that consume consumer
    projection execution capability registry events.

    A subscriber processes a single published event and performs
    domain-specific handling. It does NOT publish events, register
    itself, discover other subscribers, modify events, retry, or
    manage dispatch order. Those responsibilities belong to the
    event publisher and dispatcher.

    Every implementation must:
    - Accept exactly one registry event
    - Reject a None event by raising
      ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriberError
    - Complete synchronously
    - Never mutate the event
    - Return None

    This interface owns no business logic and provides no default
    implementation - it is a stateless, deterministic, thread-safe
    contract only.
    """

    @abstractmethod
    def handle(

        self,

        event,

    ) -> None:
        ...
