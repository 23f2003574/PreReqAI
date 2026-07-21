import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionError,
)


class _Subscriber(
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber
):
    def handle(self, event):
        return None


class TestBuildValidSubscription:
    """A valid subscription can be built from a subscriber and ID."""

    def test_build_valid_subscription(self):
        subscriber = _Subscriber()

        subscription = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
            subscriber,
            "subscription-1",
        )

        assert subscription.subscriber is subscriber
        assert subscription.subscription_id == "subscription-1"


class TestActiveSubscription:
    """A subscription defaults to active."""

    def test_active_subscription(self):
        subscription = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
            _Subscriber(),
            "subscription-1",
        )

        assert subscription.active is True


class TestInactiveSubscription:
    """A subscription can be built as explicitly inactive."""

    def test_inactive_subscription(self):
        subscription = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
            _Subscriber(),
            "subscription-1",
            active=False,
        )

        assert subscription.active is False


class TestRejectNoneSubscriber:
    """A None subscriber is rejected."""

    def test_reject_none_subscriber(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
                None,
                "subscription-1",
            )


class TestRejectEmptySubscriptionId:
    """An empty subscription ID is rejected."""

    def test_reject_empty_subscription_id(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
                _Subscriber(),
                "",
            )


class TestRejectBlankSubscriptionId:
    """A blank (whitespace-only) subscription ID is rejected."""

    def test_reject_blank_subscription_id(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
                _Subscriber(),
                "   ",
            )


class TestPreservesSubscriberReference:
    """The built subscription preserves the exact subscriber reference."""

    def test_preserves_subscriber_reference(self):
        subscriber = _Subscriber()

        subscription = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
            subscriber,
            "subscription-1",
        )

        assert subscription.subscriber is subscriber


class TestImmutableObject:
    """A subscription cannot be mutated after construction."""

    def test_immutable_object(self):
        subscription = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
            _Subscriber(),
            "subscription-1",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            subscription.active = False


class TestDeterministicConstruction:
    """Building the same inputs twice produces equal, distinct subscriptions."""

    def test_deterministic_construction(self):
        subscriber = _Subscriber()

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder()

        first = builder.build(subscriber, "subscription-1")
        second = builder.build(subscriber, "subscription-1")

        assert first == second
        assert first is not second
        assert dataclasses.is_dataclass(first)
        assert isinstance(
            first,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription,
        )


class TestCorrectFieldPopulation:
    """All fields are populated exactly as provided, with no derived state."""

    def test_correct_field_population(self):
        subscriber = _Subscriber()

        subscription = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
            subscriber,
            "subscription-42",
            active=False,
        )

        assert subscription.subscriber is subscriber
        assert subscription.subscription_id == "subscription-42"
        assert subscription.active is False
        assert {field.name for field in dataclasses.fields(subscription)} == {
            "subscriber",
            "subscription_id",
            "active",
        }
