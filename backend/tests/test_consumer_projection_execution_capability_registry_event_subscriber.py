import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriberError,
)


class _Event:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return isinstance(other, _Event) and other.name == self.name

    def __repr__(self):
        return f"_Event({self.name!r})"


class _RecordingSubscriber(
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber
):
    """A minimal, well-behaved implementation used to exercise the contract."""

    def __init__(self):
        self.handled = []

    def handle(self, event):
        if event is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriberError(
                "Cannot handle a None event."
            )

        self.handled.append(event)

        return None


class TestInterfaceIsAbstract:
    """The base subscriber class cannot be instantiated directly."""

    def test_interface_is_abstract(self):
        with pytest.raises(TypeError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber()


class TestHandleIsAbstract:
    """handle() is declared as an abstract method on the interface."""

    def test_handle_is_abstract(self):
        assert (
            "handle"
            in ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber.__abstractmethods__
        )

        assert (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber.handle.__isabstractmethod__
        )


class TestAcceptsValidEvent:
    """A concrete subscriber accepts a valid event without error."""

    def test_accepts_valid_event(self):
        subscriber = _RecordingSubscriber()
        event = _Event("registered")

        subscriber.handle(event)

        assert subscriber.handled == [event]


class TestRejectsNone:
    """A concrete subscriber rejects a None event."""

    def test_rejects_none(self):
        subscriber = _RecordingSubscriber()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriberError
        ):
            subscriber.handle(None)

        assert subscriber.handled == []


class TestReturnsNone:
    """handle() returns None on success."""

    def test_returns_none(self):
        subscriber = _RecordingSubscriber()

        result = subscriber.handle(_Event("registered"))

        assert result is None


class TestEventRemainsUnchanged:
    """Handling an event never mutates it."""

    def test_event_remains_unchanged(self):
        subscriber = _RecordingSubscriber()
        event = _Event("registered")
        original = _Event("registered")

        subscriber.handle(event)

        assert event == original


class TestConcreteImplementationInherits:
    """A concrete subclass that implements handle() can be instantiated."""

    def test_concrete_implementation_can_inherit(self):
        subscriber = _RecordingSubscriber()

        assert isinstance(
            subscriber,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
        )


class TestNoPublicationLogicExposed:
    """The interface exposes no publication-related methods."""

    def test_no_publication_logic_exposed(self):
        members = dir(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber
        )

        assert "publish" not in members
        assert "publish_batch" not in members
        assert "dispatch" not in members


class TestNoRegistryLogicExposed:
    """The interface exposes no registry- or discovery-related methods."""

    def test_no_registry_logic_exposed(self):
        members = dir(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber
        )

        assert "register" not in members
        assert "resolve" not in members
        assert "subscribe" not in members


class TestContractIsDeterministic:
    """Handling the same event twice behaves identically both times."""

    def test_repeated_handling_is_deterministic(self):
        subscriber = _RecordingSubscriber()
        event = _Event("registered")

        first = subscriber.handle(event)
        second = subscriber.handle(event)

        assert first is None
        assert second is None
        assert subscriber.handled == [event, event]
