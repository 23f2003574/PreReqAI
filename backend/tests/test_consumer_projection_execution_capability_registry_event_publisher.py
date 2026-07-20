import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisher,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisherError,
)


class _Event:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"_Event({self.name!r})"


class _Batch:
    def __init__(self, *events):
        self.events = tuple(events)


class _SpySubscriberRegistry:
    """Records resolve() calls and returns canned subscribers per event."""

    def __init__(self, calls, subscribers=()):
        self._calls = calls
        self._subscribers = subscribers
        self.call_count = 0
        self.resolved_events = []

    def resolve(self, event):
        self.call_count += 1
        self._calls.append(("resolve", event))
        self.resolved_events.append(event)
        return self._subscribers


class _SpyDispatcher:
    """Records dispatch() calls."""

    def __init__(self, calls):
        self._calls = calls
        self.call_count = 0
        self.dispatched = []

    def dispatch(self, event, subscribers):
        self.call_count += 1
        self._calls.append(("dispatch", event))
        self.dispatched.append((event, subscribers))


class _RaisingSubscriberRegistry:
    def __init__(self, error):
        self._error = error

    def resolve(self, event):
        raise self._error


class _RaisingDispatcher:
    def __init__(self, error):
        self._error = error

    def dispatch(self, event, subscribers):
        raise self._error


class TestPublishSingleEvent:
    """A single event is resolved and dispatched."""

    def test_publish_single_event(self):
        calls = []
        event = _Event("registered")
        subscribers = ("subscriber-a",)

        registry = _SpySubscriberRegistry(calls, subscribers=subscribers)
        dispatcher = _SpyDispatcher(calls)

        publisher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisher(
            registry,
            dispatcher,
        )

        result = publisher.publish(event)

        assert result is None
        assert dispatcher.dispatched == [(event, subscribers)]


class TestPublishBatch:
    """Every event in a batch is published."""

    def test_publish_batch(self):
        calls = []
        first = _Event("first")
        second = _Event("second")

        registry = _SpySubscriberRegistry(calls)
        dispatcher = _SpyDispatcher(calls)

        publisher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisher(
            registry,
            dispatcher,
        )

        result = publisher.publish_batch(_Batch(first, second))

        assert result is None
        assert registry.resolved_events == [first, second]
        assert [event for event, _ in dispatcher.dispatched] == [first, second]


class TestBatchOrderingPreserved:
    """Batch events dispatch in the exact order they were supplied."""

    def test_batch_ordering_preserved(self):
        calls = []
        events = [_Event(str(index)) for index in range(5)]

        registry = _SpySubscriberRegistry(calls)
        dispatcher = _SpyDispatcher(calls)

        publisher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisher(
            registry,
            dispatcher,
        )

        publisher.publish_batch(_Batch(*events))

        assert [event for event, _ in dispatcher.dispatched] == events


class TestSubscriberRegistryInvokedCorrectly:
    """resolve() is called once per event, with that event."""

    def test_subscriber_registry_invoked_correctly(self):
        calls = []
        event = _Event("registered")

        registry = _SpySubscriberRegistry(calls)
        dispatcher = _SpyDispatcher(calls)

        publisher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisher(
            registry,
            dispatcher,
        )

        publisher.publish(event)

        assert registry.call_count == 1
        assert registry.resolved_events == [event]


class TestDispatcherInvokedCorrectly:
    """dispatch() is called once per event, with resolved subscribers."""

    def test_dispatcher_invoked_correctly(self):
        calls = []
        event = _Event("registered")
        subscribers = ("subscriber-a", "subscriber-b")

        registry = _SpySubscriberRegistry(calls, subscribers=subscribers)
        dispatcher = _SpyDispatcher(calls)

        publisher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisher(
            registry,
            dispatcher,
        )

        publisher.publish(event)

        assert dispatcher.call_count == 1
        assert dispatcher.dispatched == [(event, subscribers)]


class TestResolveBeforeDispatch:
    """Subscribers are resolved before the event is dispatched."""

    def test_resolve_before_dispatch(self):
        calls = []

        registry = _SpySubscriberRegistry(calls)
        dispatcher = _SpyDispatcher(calls)

        publisher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisher(
            registry,
            dispatcher,
        )

        publisher.publish(_Event("registered"))

        assert calls[0][0] == "resolve"
        assert calls[1][0] == "dispatch"


class TestInvalidEventRejected:
    """A None event is rejected before any collaborator is invoked."""

    def test_invalid_event_rejected(self):
        calls = []
        registry = _SpySubscriberRegistry(calls)
        dispatcher = _SpyDispatcher(calls)

        publisher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisher(
            registry,
            dispatcher,
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisherError
        ):
            publisher.publish(None)

        assert registry.call_count == 0
        assert dispatcher.call_count == 0


class TestInvalidBatchRejected:
    """A None batch and an empty batch are both rejected."""

    def test_none_batch_rejected(self):
        calls = []
        registry = _SpySubscriberRegistry(calls)
        dispatcher = _SpyDispatcher(calls)

        publisher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisher(
            registry,
            dispatcher,
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisherError
        ):
            publisher.publish_batch(None)

        assert registry.call_count == 0
        assert dispatcher.call_count == 0

    def test_empty_batch_rejected(self):
        calls = []
        registry = _SpySubscriberRegistry(calls)
        dispatcher = _SpyDispatcher(calls)

        publisher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisher(
            registry,
            dispatcher,
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisherError
        ):
            publisher.publish_batch(_Batch())

        assert registry.call_count == 0
        assert dispatcher.call_count == 0


class TestDependenciesNotInstantiatedInternally:
    """The publisher holds only the two collaborators it was given."""

    def test_dependencies_not_instantiated_internally(self):
        calls = []
        registry = _SpySubscriberRegistry(calls)
        dispatcher = _SpyDispatcher(calls)

        publisher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisher(
            registry,
            dispatcher,
        )

        assert publisher.__dict__ == {
            "_subscriber_registry": registry,
            "_dispatcher": dispatcher,
        }


class TestErrorsPropagatedUnchanged:
    """Errors raised by collaborators propagate unwrapped."""

    def test_subscriber_registry_error_propagated(self):
        error = ValueError("cannot resolve subscribers")

        publisher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisher(
            _RaisingSubscriberRegistry(error),
            _SpyDispatcher([]),
        )

        with pytest.raises(ValueError) as excinfo:
            publisher.publish(_Event("registered"))

        assert excinfo.value is error

    def test_dispatcher_error_propagated(self):
        calls = []
        error = ValueError("cannot dispatch")

        publisher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisher(
            _SpySubscriberRegistry(calls),
            _RaisingDispatcher(error),
        )

        with pytest.raises(ValueError) as excinfo:
            publisher.publish(_Event("registered"))

        assert excinfo.value is error


class TestDeterminism:
    """Publishing the same event twice produces the same collaborator calls."""

    def test_repeated_publish_is_deterministic(self):
        calls = []
        event = _Event("registered")
        subscribers = ("subscriber-a",)

        registry = _SpySubscriberRegistry(calls, subscribers=subscribers)
        dispatcher = _SpyDispatcher(calls)

        publisher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublisher(
            registry,
            dispatcher,
        )

        publisher.publish(event)
        publisher.publish(event)

        assert dispatcher.dispatched == [
            (event, subscribers),
            (event, subscribers),
        ]
