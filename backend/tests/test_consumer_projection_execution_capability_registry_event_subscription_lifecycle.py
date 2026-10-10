import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
)


class _Subscriber(
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber
):
    def handle(self, event):
        return None


def _subscription(name="subscription"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
        _Subscriber(),
        name,
    )


class TestBuildRegisteredLifecycle:
    """A REGISTERED lifecycle can be built for a subscription."""

    def test_build_registered_lifecycle(self):
        subscription = _subscription()

        lifecycle = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder().build(
            subscription,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
        )

        assert (
            lifecycle.state
            == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED
        )


class TestBuildActiveLifecycle:
    """An ACTIVE lifecycle can be built for a subscription."""

    def test_build_active_lifecycle(self):
        subscription = _subscription()

        lifecycle = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder().build(
            subscription,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        )

        assert (
            lifecycle.state
            == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE
        )


class TestBuildSuspendedLifecycle:
    """A SUSPENDED lifecycle can be built for a subscription."""

    def test_build_suspended_lifecycle(self):
        subscription = _subscription()

        lifecycle = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder().build(
            subscription,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.SUSPENDED,
        )

        assert (
            lifecycle.state
            == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.SUSPENDED
        )


class TestBuildUnregisteredLifecycle:
    """An UNREGISTERED lifecycle can be built for a subscription."""

    def test_build_unregistered_lifecycle(self):
        subscription = _subscription()

        lifecycle = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder().build(
            subscription,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.UNREGISTERED,
        )

        assert (
            lifecycle.state
            == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.UNREGISTERED
        )


class TestRejectNoneSubscription:
    """A None subscription is rejected."""

    def test_reject_none_subscription(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder().build(
                None,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            )


class TestRejectNoneState:
    """A None lifecycle state is rejected."""

    def test_reject_none_state(self):
        subscription = _subscription()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder().build(
                subscription,
                None,
            )


class TestPreserveSubscriptionReference:
    """The lifecycle preserves the exact subscription reference passed in."""

    def test_preserve_subscription_reference(self):
        subscription = _subscription()

        lifecycle = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder().build(
            subscription,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        )

        assert lifecycle.subscription is subscription


class TestImmutableLifecycle:
    """A built lifecycle cannot have its fields reassigned."""

    def test_immutable_lifecycle(self):
        subscription = _subscription()

        lifecycle = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder().build(
            subscription,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            lifecycle.state = (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.SUSPENDED
            )


class TestCorrectStateAssignment:
    """The lifecycle's state exactly matches the state passed to the builder."""

    @pytest.mark.parametrize(
        "state",
        [
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.SUSPENDED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.UNREGISTERED,
        ],
    )
    def test_correct_state_assignment(self, state):
        subscription = _subscription()

        lifecycle = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder().build(
            subscription,
            state,
        )

        assert lifecycle.state == state


class TestDeterministicConstruction:
    """Building the same inputs twice produces equal, distinct lifecycles."""

    def test_deterministic_construction(self):
        subscription = _subscription()

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder()

        first = builder.build(
            subscription,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        )
        second = builder.build(
            subscription,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        )

        assert first == second
        assert first is not second
        assert dataclasses.is_dataclass(first)
        assert isinstance(
            first,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle,
        )
