import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidator,
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


def _transition(from_state, to_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder().build(
        _subscription(),
        from_state,
        to_state,
    )


class TestAllowedTransitions:
    """Every permitted transition passes validation without raising."""

    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            (_STATE.REGISTERED, _STATE.ACTIVE),
            (_STATE.ACTIVE, _STATE.SUSPENDED),
            (_STATE.SUSPENDED, _STATE.ACTIVE),
            (_STATE.REGISTERED, _STATE.UNREGISTERED),
            (_STATE.ACTIVE, _STATE.UNREGISTERED),
            (_STATE.SUSPENDED, _STATE.UNREGISTERED),
        ],
    )
    def test_allowed_transitions(self, from_state, to_state):
        transition = _transition(from_state, to_state)

        assert (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidator().validate(
                transition
            )
            is None
        )


class TestRejectedTransitions:
    """Every unsupported transition raises a validation error."""

    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            (_STATE.REGISTERED, _STATE.SUSPENDED),
            (_STATE.ACTIVE, _STATE.REGISTERED),
            (_STATE.SUSPENDED, _STATE.REGISTERED),
            (_STATE.UNREGISTERED, _STATE.ACTIVE),
            (_STATE.UNREGISTERED, _STATE.REGISTERED),
            (_STATE.UNREGISTERED, _STATE.SUSPENDED),
        ],
    )
    def test_rejected_transitions(self, from_state, to_state):
        transition = _transition(from_state, to_state)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidationError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidator().validate(
                transition
            )


class TestRejectNoneTransition:
    """A None transition is rejected."""

    def test_reject_none_transition(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidationError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidator().validate(
                None
            )


class TestDeterministicValidation:
    """Validating the same transition twice produces the same outcome."""

    def test_deterministic_validation(self):
        transition = _transition(_STATE.REGISTERED, _STATE.ACTIVE)

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidator()

        assert validator.validate(transition) is None
        assert validator.validate(transition) is None
