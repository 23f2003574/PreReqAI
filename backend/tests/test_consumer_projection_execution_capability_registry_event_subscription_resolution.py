import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolution,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionError,
)


class _Subscriber(
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber
):
    def handle(self, event):
        return None


class _Event:
    def __init__(self, name):
        self.name = name


def _subscription(subscription_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
        _Subscriber(),
        subscription_id,
    )


class TestBuildEmptyResolution:
    """A resolution can be built with no subscriptions."""

    def test_build_empty_resolution(self):
        event = _Event("registered")

        resolution = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder().build(
            event,
            (),
        )

        assert resolution.event is event
        assert resolution.subscriptions == ()
        assert resolution.resolved_subscription_count == 0


class TestBuildSingleSubscriptionResolution:
    """A resolution can be built with a single subscription."""

    def test_build_single_subscription_resolution(self):
        event = _Event("registered")
        subscription = _subscription("subscription-1")

        resolution = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder().build(
            event,
            (subscription,),
        )

        assert resolution.subscriptions == (subscription,)
        assert resolution.resolved_subscription_count == 1


class TestBuildMultiSubscriptionResolution:
    """A resolution can be built with multiple subscriptions."""

    def test_build_multi_subscription_resolution(self):
        event = _Event("registered")
        first = _subscription("subscription-1")
        second = _subscription("subscription-2")

        resolution = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder().build(
            event,
            (first, second),
        )

        assert resolution.subscriptions == (first, second)
        assert resolution.resolved_subscription_count == 2


class TestCorrectResolvedSubscriptionCount:
    """resolved_subscription_count always mirrors len(subscriptions)."""

    @pytest.mark.parametrize("count", [0, 1, 4])
    def test_correct_resolved_subscription_count(self, count):
        event = _Event("registered")
        subscriptions = tuple(
            _subscription(f"subscription-{index}") for index in range(count)
        )

        resolution = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder().build(
            event,
            subscriptions,
        )

        assert resolution.resolved_subscription_count == count


class TestPreserveSubscriptionOrdering:
    """Subscription ordering is preserved exactly."""

    def test_preserve_subscription_ordering(self):
        event = _Event("registered")
        subscriptions = (
            _subscription("subscription-3"),
            _subscription("subscription-1"),
            _subscription("subscription-2"),
        )

        resolution = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder().build(
            event,
            subscriptions,
        )

        assert resolution.subscriptions == subscriptions


class TestRejectNoneEvent:
    """A None event is rejected."""

    def test_reject_none_event(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder().build(
                None,
                (),
            )


class TestRejectNoneSubscriptionCollection:
    """A None subscription collection is rejected."""

    def test_reject_none_subscription_collection(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder().build(
                _Event("registered"),
                None,
            )


class TestRejectNoneSubscriptionEntry:
    """A None entry within the subscription collection is rejected."""

    def test_reject_none_subscription_entry(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder().build(
                _Event("registered"),
                (_subscription("subscription-1"), None),
            )


class TestImmutableResult:
    """A resolution cannot be mutated after construction."""

    def test_immutable_result(self):
        resolution = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder().build(
            _Event("registered"),
            (),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            resolution.resolved_subscription_count = 5


class TestDeterministicConstruction:
    """Building the same inputs twice produces equal, distinct resolutions."""

    def test_deterministic_construction(self):
        event = _Event("registered")
        subscriptions = (_subscription("subscription-1"),)

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder()

        first = builder.build(event, subscriptions)
        second = builder.build(event, subscriptions)

        assert first == second
        assert first is not second
        assert dataclasses.is_dataclass(first)
        assert isinstance(
            first,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolution,
        )
