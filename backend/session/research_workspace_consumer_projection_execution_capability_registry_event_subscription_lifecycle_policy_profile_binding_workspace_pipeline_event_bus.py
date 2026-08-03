from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_event_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_event import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEvent,
    VALID_PIPELINE_EVENT_TYPES,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_event_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventBus:
    """
    Decouples consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace pipeline
    execution from downstream notification and audit consumers: a
    pipeline publishes lifecycle events onto the bus instead of
    invoking those consumers directly, and each consumer subscribes
    to the event types it cares about.

    The bus's responsibility is queuing, subscription bookkeeping,
    and dispatch, not interpreting an event's payload or deciding
    what a subscriber should do with it. It does NOT execute stages
    or pipelines, and does NOT retry a failed subscriber.

    Behavior:
    - publish() enqueues an event in FIFO order; publishing an event
      whose ID has already been queued or already dispatched is a
      no-op, so a retried publish() call can never deliver an event
      twice
    - dispatch_pending() delivers every currently queued event, in
      the order it was published, to every handler subscribed to its
      event type, then drains the queue, so a later
      dispatch_pending() call never redelivers an already-dispatched
      event
    - A subscriber whose handler raises does not prevent delivery to
      the event's other subscribers, and does not stop dispatch of
      later events

    The bus is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock; subscriber handlers run outside the lock, so a handler
      that calls back into the bus cannot deadlock it
    """

    def __init__(self):
        self._subscribers = {}
        self._pending = []
        self._delivered_event_ids = set()
        self._lock = RLock()

    def publish(
        self,
        event: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEvent,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventResult:
        """
        Queue an event for dispatch.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError:
                If event is None or not a ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEvent
        """

        if event is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                "Cannot publish a None pipeline event."
            )

        if not isinstance(event, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEvent):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                "Cannot publish a pipeline event: event must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEvent."
            )

        with self._lock:
            already_seen = event.event_id in self._delivered_event_ids or any(
                queued.event_id == event.event_id for queued in self._pending
            )

            if already_seen:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventResult(published=False, subscribers_notified=0)

            self._pending.append(event)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventResult(published=True, subscribers_notified=0)

    def subscribe(self, event_type: str, handler) -> None:
        """
        Register a handler to receive every future dispatch of a
        given event type.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError:
                If event_type is None, blank, or not a recognized
                event type, handler is not callable, or handler is
                already subscribed to event_type
        """

        self._validate_event_type(event_type)
        self._validate_handler(handler)

        with self._lock:
            handlers = self._subscribers.setdefault(event_type, [])

            if handler in handlers:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                    f"Handler is already subscribed to event type {event_type!r}."
                )

            handlers.append(handler)

    def unsubscribe(self, event_type: str, handler) -> None:
        """
        Remove a handler from an event type's subscribers.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError:
                If event_type is None, blank, or not a recognized
                event type, handler is not callable, or handler is
                not currently subscribed to event_type
        """

        self._validate_event_type(event_type)
        self._validate_handler(handler)

        with self._lock:
            handlers = self._subscribers.get(event_type, [])

            if handler not in handlers:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                    f"Handler is not subscribed to event type {event_type!r}."
                )

            handlers.remove(handler)

    def dispatch_pending(self) -> tuple:
        """
        Dispatch every currently queued event, in FIFO order, to the
        handlers subscribed to each event's type, then drain the
        queue.

        Returns:
            One result per dispatched event, in dispatch order
        """

        with self._lock:
            to_dispatch = list(self._pending)
            self._pending = []

        results = []

        for event in to_dispatch:
            with self._lock:
                handlers = tuple(self._subscribers.get(event.event_type, ()))

            notified = 0

            for handler in handlers:
                try:
                    handler(event)
                    notified += 1
                except Exception:
                    continue

            with self._lock:
                self._delivered_event_ids.add(event.event_id)

            results.append(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventResult(published=True, subscribers_notified=notified))

        return tuple(results)

    def pending_events(self) -> tuple:
        """
        List every event queued but not yet dispatched, in FIFO
        order.
        """

        with self._lock:
            return tuple(self._pending)

    def _validate_event_type(self, event_type: str) -> None:
        if event_type is None or not event_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                "Cannot operate with an empty or blank event type."
            )

        if event_type not in VALID_PIPELINE_EVENT_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                f"Invalid pipeline event type {event_type!r}. Must be one of "
                f"{VALID_PIPELINE_EVENT_TYPES!r}."
            )

    def _validate_handler(self, handler) -> None:
        if not callable(handler):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                "Cannot operate with a handler that is not callable."
            )
