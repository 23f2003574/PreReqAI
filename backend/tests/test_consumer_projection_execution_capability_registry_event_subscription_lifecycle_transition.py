import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionError,
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


_STATE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState


class TestBuildRegisteredToActiveTransition:
    """A REGISTERED -> ACTIVE transition can be built."""

    def test_build_registered_to_active_transition(self):
        subscription = _subscription()

        transition = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder().build(
            subscription,
            _STATE.REGISTERED,
            _STATE.ACTIVE,
        )

        assert transition.from_state == _STATE.REGISTERED
        assert transition.to_state == _STATE.ACTIVE


class TestBuildActiveToSuspendedTransition:
    """An ACTIVE -> SUSPENDED transition can be built."""

    def test_build_active_to_suspended_transition(self):
        subscription = _subscription()

        transition = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder().build(
            subscription,
            _STATE.ACTIVE,
            _STATE.SUSPENDED,
        )

        assert transition.from_state == _STATE.ACTIVE
        assert transition.to_state == _STATE.SUSPENDED


class TestBuildSuspendedToActiveTransition:
    """A SUSPENDED -> ACTIVE transition can be built."""

    def test_build_suspended_to_active_transition(self):
        subscription = _subscription()

        transition = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder().build(
            subscription,
            _STATE.SUSPENDED,
            _STATE.ACTIVE,
        )

        assert transition.from_state == _STATE.SUSPENDED
        assert transition.to_state == _STATE.ACTIVE


class TestBuildActiveToUnregisteredTransition:
    """An ACTIVE -> UNREGISTERED transition can be built."""

    def test_build_active_to_unregistered_transition(self):
        subscription = _subscription()

        transition = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder().build(
            subscription,
            _STATE.ACTIVE,
            _STATE.UNREGISTERED,
        )

        assert transition.from_state == _STATE.ACTIVE
        assert transition.to_state == _STATE.UNREGISTERED


class TestRejectNoneSubscription:
    """A None subscription is rejected."""

    def test_reject_none_subscription(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder().build(
                None,
                _STATE.REGISTERED,
                _STATE.ACTIVE,
            )


class TestRejectNoneFromState:
    """A None from_state is rejected."""

    def test_reject_none_from_state(self):
        subscription = _subscription()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder().build(
                subscription,
                None,
                _STATE.ACTIVE,
            )


class TestRejectNoneToState:
    """A None to_state is rejected."""

    def test_reject_none_to_state(self):
        subscription = _subscription()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder().build(
                subscription,
                _STATE.REGISTERED,
                None,
            )


class TestRejectIdenticalStates:
    """Identical from_state and to_state are rejected."""

    @pytest.mark.parametrize(
        "state",
        [_STATE.REGISTERED, _STATE.ACTIVE, _STATE.SUSPENDED, _STATE.UNREGISTERED],
    )
    def test_reject_identical_states(self, state):
        subscription = _subscription()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder().build(
                subscription,
                state,
                state,
            )


class TestImmutableTransition:
    """A built transition cannot have its fields reassigned."""

    def test_immutable_transition(self):
        subscription = _subscription()

        transition = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder().build(
            subscription,
            _STATE.REGISTERED,
            _STATE.ACTIVE,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            transition.to_state = _STATE.SUSPENDED


class TestDeterministicConstruction:
    """Building the same inputs twice produces equal, distinct transitions."""

    def test_deterministic_construction(self):
        subscription = _subscription()

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder()

        first = builder.build(
            subscription,
            _STATE.REGISTERED,
            _STATE.ACTIVE,
        )
        second = builder.build(
            subscription,
            _STATE.REGISTERED,
            _STATE.ACTIVE,
        )

        assert first == second
        assert first is not second
        assert dataclasses.is_dataclass(first)
        assert isinstance(
            first,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition,
        )
