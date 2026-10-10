import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSession,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionError,
)


class _Subscriber(
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber
):
    def handle(self, event):
        return None


class _Event:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"_Event({self.name!r})"


def _subscription(subscription_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
        _Subscriber(),
        subscription_id,
    )


def _resolution(event, *subscription_ids):
    subscriptions = tuple(
        _subscription(subscription_id) for subscription_id in subscription_ids
    )

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder().build(
        event,
        subscriptions,
    )


class TestBuildValidSession:
    """A well-formed input set builds a matching resolution session."""

    def test_build_valid_session(self):
        event = _Event("registered")
        resolution = _resolution(event, "subscription-1")

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionBuilder().build(
            event,
            resolution,
        )

        assert session.event is event
        assert session.resolution is resolution


class TestEmptyResolutionSession:
    """A resolution with no subscriptions produces a completed session."""

    def test_empty_resolution_session(self):
        event = _Event("registered")
        resolution = _resolution(event)

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionBuilder().build(
            event,
            resolution,
        )

        assert session.resolved_subscription_count == 0
        assert session.resolution_completed is True


class TestMultiSubscriptionSession:
    """A resolution with multiple subscriptions is reflected in the session."""

    def test_multi_subscription_session(self):
        event = _Event("registered")
        resolution = _resolution(event, "subscription-1", "subscription-2")

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionBuilder().build(
            event,
            resolution,
        )

        assert session.resolved_subscription_count == 2


class TestCorrectResolvedSubscriptionCount:
    """resolved_subscription_count mirrors resolution.resolved_subscription_count."""

    @pytest.mark.parametrize("count", [0, 1, 4])
    def test_correct_resolved_subscription_count(self, count):
        event = _Event("registered")
        resolution = _resolution(
            event,
            *[f"subscription-{index}" for index in range(count)],
        )

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionBuilder().build(
            event,
            resolution,
        )

        assert session.resolved_subscription_count == count
        assert (
            session.resolved_subscription_count
            == resolution.resolved_subscription_count
        )


class TestResolutionMarkedCompleted:
    """resolution_completed is always True for a built session."""

    def test_resolution_marked_completed(self):
        event = _Event("registered")
        resolution = _resolution(event, "subscription-1")

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionBuilder().build(
            event,
            resolution,
        )

        assert session.resolution_completed is True


class TestRejectNoneEvent:
    """A None event is rejected."""

    def test_reject_none_event(self):
        resolution = _resolution(_Event("registered"), "subscription-1")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionBuilder().build(
                None,
                resolution,
            )


class TestRejectNoneResolution:
    """A None resolution is rejected."""

    def test_reject_none_resolution(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionBuilder().build(
                _Event("registered"),
                None,
            )


class TestRejectEventMismatch:
    """A resolution built for a different event is rejected."""

    def test_reject_event_mismatch(self):
        session_event = _Event("registered")
        resolution = _resolution(_Event("removed"), "subscription-1")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionBuilder().build(
                session_event,
                resolution,
            )


class TestImmutableAndDeterministicSession:
    """The session is a frozen dataclass and repeated builds agree."""

    def test_immutable_session(self):
        event = _Event("registered")
        resolution = _resolution(event, "subscription-1")

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionBuilder().build(
            event,
            resolution,
        )

        assert dataclasses.is_dataclass(session)
        assert isinstance(
            session,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSession,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            session.resolution_completed = False

    def test_repeated_build_is_deterministic(self):
        event = _Event("registered")
        resolution = _resolution(event, "subscription-1", "subscription-2")

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionBuilder()

        first = builder.build(event, resolution)
        second = builder.build(event, resolution)

        assert first == second
        assert first is not second
