import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcher,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcherError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
)


class _Event:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"_Event({self.name!r})"


class _RecordingSubscriber(
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber
):
    def __init__(self, name, calls):
        self._name = name
        self._calls = calls
        self.call_count = 0

    def handle(self, event):
        self.call_count += 1
        self._calls.append((self._name, event))
        return None


class _RaisingSubscriber(
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber
):
    def __init__(self, name, calls, error):
        self._name = name
        self._calls = calls
        self._error = error
        self.call_count = 0

    def handle(self, event):
        self.call_count += 1
        self._calls.append((self._name, event))
        raise self._error


class TestDispatchToOneSubscriber:
    """A single subscriber is handed the event."""

    def test_dispatch_to_one_subscriber(self):
        calls = []
        event = _Event("registered")
        subscriber = _RecordingSubscriber("a", calls)

        dispatcher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcher()

        result = dispatcher.dispatch(event, (subscriber,))

        assert result is None
        assert calls == [("a", event)]


class TestDispatchToMultipleSubscribers:
    """Every subscriber in the collection receives the event."""

    def test_dispatch_to_multiple_subscribers(self):
        calls = []
        event = _Event("registered")
        first = _RecordingSubscriber("a", calls)
        second = _RecordingSubscriber("b", calls)
        third = _RecordingSubscriber("c", calls)

        dispatcher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcher()

        dispatcher.dispatch(event, (first, second, third))

        assert calls == [
            ("a", event),
            ("b", event),
            ("c", event),
        ]


class TestRegistrationOrderPreserved:
    """Subscribers are invoked in exactly the order supplied."""

    def test_registration_order_preserved(self):
        calls = []
        event = _Event("registered")
        subscribers = tuple(
            _RecordingSubscriber(str(index), calls) for index in range(5)
        )

        dispatcher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcher()

        dispatcher.dispatch(event, subscribers)

        assert [name for name, _ in calls] == ["0", "1", "2", "3", "4"]


class TestEverySubscriberInvokedExactlyOnce:
    """Each subscriber's handle() is called exactly once."""

    def test_every_subscriber_invoked_exactly_once(self):
        calls = []
        event = _Event("registered")
        first = _RecordingSubscriber("a", calls)
        second = _RecordingSubscriber("b", calls)

        dispatcher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcher()

        dispatcher.dispatch(event, (first, second))

        assert first.call_count == 1
        assert second.call_count == 1


class TestRejectNoneEvent:
    """A None event is rejected before any subscriber is invoked."""

    def test_reject_none_event(self):
        calls = []
        subscriber = _RecordingSubscriber("a", calls)

        dispatcher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcher()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcherError
        ):
            dispatcher.dispatch(None, (subscriber,))

        assert subscriber.call_count == 0


class TestRejectNoneSubscriberCollection:
    """A None subscriber collection is rejected."""

    def test_reject_none_subscriber_collection(self):
        dispatcher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcher()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcherError
        ):
            dispatcher.dispatch(_Event("registered"), None)


class TestRejectNoneSubscriberEntry:
    """A None entry within the subscriber collection is rejected."""

    def test_reject_none_subscriber_entry(self):
        calls = []
        event = _Event("registered")
        subscriber = _RecordingSubscriber("a", calls)

        dispatcher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcher()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcherError
        ):
            dispatcher.dispatch(event, (subscriber, None))

        assert subscriber.call_count == 0


class TestSubscriberExceptionPropagatedUnchanged:
    """An exception raised by a subscriber propagates unwrapped."""

    def test_subscriber_exception_propagated_unchanged(self):
        calls = []
        event = _Event("registered")
        error = ValueError("subscriber blew up")
        subscriber = _RaisingSubscriber("a", calls, error)

        dispatcher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcher()

        with pytest.raises(ValueError) as excinfo:
            dispatcher.dispatch(event, (subscriber,))

        assert excinfo.value is error


class TestDispatchStopsOnFirstFailure:
    """No later subscriber is invoked once one raises."""

    def test_dispatch_stops_on_first_failure(self):
        calls = []
        event = _Event("registered")
        error = ValueError("subscriber blew up")

        first = _RecordingSubscriber("a", calls)
        failing = _RaisingSubscriber("b", calls, error)
        third = _RecordingSubscriber("c", calls)

        dispatcher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcher()

        with pytest.raises(ValueError):
            dispatcher.dispatch(event, (first, failing, third))

        assert first.call_count == 1
        assert failing.call_count == 1
        assert third.call_count == 0
        assert calls == [("a", event), ("b", event)]


class TestDeterminism:
    """Dispatching the same event and subscribers twice agrees."""

    def test_repeated_dispatch_is_deterministic(self):
        calls = []
        event = _Event("registered")
        subscriber = _RecordingSubscriber("a", calls)

        dispatcher = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatcher()

        dispatcher.dispatch(event, (subscriber,))
        dispatcher.dispatch(event, (subscriber,))

        assert calls == [("a", event), ("a", event)]
        assert subscriber.call_count == 2
