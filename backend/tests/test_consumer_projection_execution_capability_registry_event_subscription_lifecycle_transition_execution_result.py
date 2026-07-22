import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError,
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


def _lifecycle(subscription, state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder().build(
        subscription,
        state,
    )


def _transition(subscription, from_state, to_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder().build(
        subscription,
        from_state,
        to_state,
    )


def _valid_result_inputs(subscription=None):
    subscription = subscription or _subscription()

    previous_lifecycle = _lifecycle(subscription, _STATE.REGISTERED)
    transition = _transition(subscription, _STATE.REGISTERED, _STATE.ACTIVE)
    resulting_lifecycle = _lifecycle(subscription, _STATE.ACTIVE)

    return previous_lifecycle, transition, resulting_lifecycle


class TestBuildValidExecutionResult:
    """A consistent previous/transition/resulting triple builds a result."""

    def test_build_valid_execution_result(self):
        previous_lifecycle, transition, resulting_lifecycle = (
            _valid_result_inputs()
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultBuilder().build(
            previous_lifecycle,
            transition,
            resulting_lifecycle,
        )

        assert result.previous_lifecycle is previous_lifecycle
        assert result.transition is transition
        assert result.resulting_lifecycle is resulting_lifecycle


class TestRejectNonePreviousLifecycle:
    """A None previous lifecycle is rejected."""

    def test_reject_none_previous_lifecycle(self):
        _, transition, resulting_lifecycle = _valid_result_inputs()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultBuilder().build(
                None,
                transition,
                resulting_lifecycle,
            )


class TestRejectNoneTransition:
    """A None transition is rejected."""

    def test_reject_none_transition(self):
        previous_lifecycle, _, resulting_lifecycle = _valid_result_inputs()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultBuilder().build(
                previous_lifecycle,
                None,
                resulting_lifecycle,
            )


class TestRejectNoneResultingLifecycle:
    """A None resulting lifecycle is rejected."""

    def test_reject_none_resulting_lifecycle(self):
        previous_lifecycle, transition, _ = _valid_result_inputs()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultBuilder().build(
                previous_lifecycle,
                transition,
                None,
            )


class TestRejectPreviousLifecycleSubscriptionMismatch:
    """A previous lifecycle for a different subscription is rejected."""

    def test_reject_previous_lifecycle_subscription_mismatch(self):
        _, transition, resulting_lifecycle = _valid_result_inputs()

        mismatched_previous = _lifecycle(
            _subscription("other"),
            _STATE.REGISTERED,
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultBuilder().build(
                mismatched_previous,
                transition,
                resulting_lifecycle,
            )


class TestRejectResultingLifecycleSubscriptionMismatch:
    """A resulting lifecycle for a different subscription is rejected."""

    def test_reject_resulting_lifecycle_subscription_mismatch(self):
        previous_lifecycle, transition, _ = _valid_result_inputs()

        mismatched_resulting = _lifecycle(
            _subscription("other"),
            _STATE.ACTIVE,
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultBuilder().build(
                previous_lifecycle,
                transition,
                mismatched_resulting,
            )


class TestRejectPreviousStateMismatch:
    """A previous lifecycle whose state differs from transition.from_state is rejected."""

    def test_reject_previous_state_mismatch(self):
        subscription = _subscription()
        transition = _transition(subscription, _STATE.REGISTERED, _STATE.ACTIVE)
        resulting_lifecycle = _lifecycle(subscription, _STATE.ACTIVE)

        mismatched_previous = _lifecycle(subscription, _STATE.SUSPENDED)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultBuilder().build(
                mismatched_previous,
                transition,
                resulting_lifecycle,
            )


class TestRejectResultingStateMismatch:
    """A resulting lifecycle whose state differs from transition.to_state is rejected."""

    def test_reject_resulting_state_mismatch(self):
        subscription = _subscription()
        previous_lifecycle = _lifecycle(subscription, _STATE.REGISTERED)
        transition = _transition(subscription, _STATE.REGISTERED, _STATE.ACTIVE)

        mismatched_resulting = _lifecycle(subscription, _STATE.SUSPENDED)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultBuilder().build(
                previous_lifecycle,
                transition,
                mismatched_resulting,
            )


class TestImmutableConstruction:
    """A built execution result cannot have its fields reassigned."""

    def test_immutable_construction(self):
        previous_lifecycle, transition, resulting_lifecycle = (
            _valid_result_inputs()
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultBuilder().build(
            previous_lifecycle,
            transition,
            resulting_lifecycle,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.resulting_lifecycle = previous_lifecycle


class TestDeterministicConstruction:
    """Building the same inputs twice produces equal, distinct results."""

    def test_deterministic_construction(self):
        previous_lifecycle, transition, resulting_lifecycle = (
            _valid_result_inputs()
        )

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultBuilder()

        first = builder.build(previous_lifecycle, transition, resulting_lifecycle)
        second = builder.build(previous_lifecycle, transition, resulting_lifecycle)

        assert first == second
        assert first is not second
        assert dataclasses.is_dataclass(first)
        assert isinstance(
            first,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResult,
        )
