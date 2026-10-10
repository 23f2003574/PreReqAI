import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolverError,
)


class _Subscriber(
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber
):
    def handle(self, event):
        return None


class _Event:
    def __init__(self, name):
        self.name = name


def _subscription(subscription_id, active=True):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
        _Subscriber(),
        subscription_id,
        active=active,
    )


class TestResolveSingleActiveSubscription:
    """A single active subscription is resolved."""

    def test_resolve_single_active_subscription(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        subscription = _subscription("subscription-1")
        registry.register(subscription)

        resolved = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolver().resolve(
            registry,
            _Event("registered"),
        )

        assert resolved == (subscription,)


class TestResolveMultipleActiveSubscriptions:
    """Multiple active subscriptions are all resolved."""

    def test_resolve_multiple_active_subscriptions(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        first = _subscription("subscription-1")
        second = _subscription("subscription-2")
        registry.register(first)
        registry.register(second)

        resolved = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolver().resolve(
            registry,
            _Event("registered"),
        )

        assert resolved == (first, second)


class TestIgnoreInactiveSubscriptions:
    """Inactive subscriptions are excluded from resolution."""

    def test_ignore_inactive_subscriptions(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        active = _subscription("subscription-1", active=True)
        inactive = _subscription("subscription-2", active=False)
        registry.register(active)
        registry.register(inactive)

        resolved = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolver().resolve(
            registry,
            _Event("registered"),
        )

        assert resolved == (active,)


class TestEmptyRegistryReturnsEmptyTuple:
    """An empty registry resolves to an empty tuple."""

    def test_empty_registry_returns_empty_tuple(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()

        resolved = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolver().resolve(
            registry,
            _Event("registered"),
        )

        assert resolved == ()


class TestRegistrationOrderPreserved:
    """Resolved subscriptions preserve registration order."""

    def test_registration_order_preserved(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        first = _subscription("subscription-1")
        second = _subscription("subscription-2")
        third = _subscription("subscription-3")
        registry.register(first)
        registry.register(second)
        registry.register(third)

        resolved = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolver().resolve(
            registry,
            _Event("registered"),
        )

        assert resolved == (first, second, third)


class TestReturnedTupleIsImmutable:
    """The resolver returns a plain, immutable tuple."""

    def test_returned_tuple_is_immutable(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        registry.register(_subscription("subscription-1"))

        resolved = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolver().resolve(
            registry,
            _Event("registered"),
        )

        assert isinstance(resolved, tuple)

        with pytest.raises(TypeError):
            resolved[0] = None


class TestRejectNoneRegistry:
    """A None registry is rejected."""

    def test_reject_none_registry(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolverError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolver().resolve(
                None,
                _Event("registered"),
            )


class TestRejectNoneEvent:
    """A None event is rejected."""

    def test_reject_none_event(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolverError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolver().resolve(
                registry,
                None,
            )


class TestRegistryRemainsUnchanged:
    """Resolving does not mutate the registry's registered subscriptions."""

    def test_registry_remains_unchanged(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        subscription = _subscription("subscription-1")
        registry.register(subscription)
        before = registry.subscriptions()

        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolver().resolve(
            registry,
            _Event("registered"),
        )

        assert registry.subscriptions() == before


class TestDeterministicResolution:
    """Resolving the same registry and event twice yields equal results."""

    def test_deterministic_resolution(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionRegistry()
        registry.register(_subscription("subscription-1"))
        registry.register(_subscription("subscription-2", active=False))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolver()
        event = _Event("registered")

        first = resolver.resolve(registry, event)
        second = resolver.resolve(registry, event)

        assert first == second
