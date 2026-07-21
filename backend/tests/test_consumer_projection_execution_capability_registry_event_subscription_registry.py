import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistryError,
)


class _Subscriber(
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber
):
    def handle(self, event):
        return None


def _subscription(subscription_id, active=True):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
        _Subscriber(),
        subscription_id,
        active=active,
    )


class TestRegisterSubscription:
    """A single subscription can be registered and later found."""

    def test_register_subscription(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        subscription = _subscription("subscription-1")

        registry.register(subscription)

        assert registry.find("subscription-1") is subscription


class TestRegisterMultipleSubscriptions:
    """Multiple distinct subscriptions can all be registered."""

    def test_register_multiple_subscriptions(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        first = _subscription("subscription-1")
        second = _subscription("subscription-2")

        registry.register(first)
        registry.register(second)

        assert registry.subscriptions() == (first, second)


class TestRejectDuplicateSubscriptionId:
    """Registering a second subscription with the same ID is rejected."""

    def test_reject_duplicate_subscription_id(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        registry.register(_subscription("subscription-1"))

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistryError
        ):
            registry.register(_subscription("subscription-1"))

        assert len(registry.subscriptions()) == 1


class TestRejectNoneSubscription:
    """Registering a None subscription is rejected."""

    def test_reject_none_subscription(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistryError
        ):
            registry.register(None)


class TestUnregisterExistingSubscription:
    """Unregistering an existing subscription removes it."""

    def test_unregister_existing_subscription(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        registry.register(_subscription("subscription-1"))

        registry.unregister("subscription-1")

        assert registry.find("subscription-1") is None
        assert registry.subscriptions() == ()


class TestUnregisterMissingSubscription:
    """Unregistering a subscription ID that was never registered is a no-op."""

    def test_unregister_missing_subscription(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        subscription = _subscription("subscription-1")
        registry.register(subscription)

        registry.unregister("does-not-exist")

        assert registry.subscriptions() == (subscription,)


class TestFindExistingSubscription:
    """find() returns the matching subscription when registered."""

    def test_find_existing_subscription(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        subscription = _subscription("subscription-1")
        registry.register(subscription)

        assert registry.find("subscription-1") is subscription


class TestFindMissingSubscription:
    """find() returns None when no subscription matches."""

    def test_find_missing_subscription(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()

        assert registry.find("does-not-exist") is None


class TestRegistrationOrderPreserved:
    """subscriptions() reflects insertion order."""

    def test_registration_order_preserved(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        first = _subscription("subscription-1")
        second = _subscription("subscription-2")
        third = _subscription("subscription-3")

        registry.register(first)
        registry.register(second)
        registry.register(third)

        assert registry.subscriptions() == (first, second, third)


class TestImmutableSnapshotReturned:
    """subscriptions() returns a tuple that does not alias mutable state."""

    def test_immutable_snapshot_returned(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        registry.register(_subscription("subscription-1"))

        snapshot = registry.subscriptions()

        assert isinstance(snapshot, tuple)

        registry.register(_subscription("subscription-2"))

        assert snapshot == (registry.find("subscription-1"),)
        assert len(registry.subscriptions()) == 2


class TestDeterministicBehavior:
    """Identical operation sequences produce identical observable state."""

    def test_deterministic_behavior(self):
        first_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        second_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()

        subscriptions = [
            _subscription("subscription-1"),
            _subscription("subscription-2"),
        ]

        for subscription in subscriptions:

            first_registry.register(subscription)
            second_registry.register(subscription)

        first_registry.unregister("subscription-1")
        second_registry.unregister("subscription-1")

        assert (
            first_registry.subscriptions()
            == second_registry.subscriptions()
        )
