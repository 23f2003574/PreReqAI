import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutor,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutorError,
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


def _executor():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutor(
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidator(),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder(),
    )


class TestExecuteRegisteredToActive:
    """Executing REGISTERED -> ACTIVE produces an ACTIVE lifecycle."""

    def test_execute_registered_to_active(self):
        subscription = _subscription()
        lifecycle = _lifecycle(subscription, _STATE.REGISTERED)
        transition = _transition(subscription, _STATE.REGISTERED, _STATE.ACTIVE)

        result = _executor().execute(lifecycle, transition)

        assert result.subscription == subscription
        assert result.state == _STATE.ACTIVE


class TestExecuteActiveToSuspended:
    """Executing ACTIVE -> SUSPENDED produces a SUSPENDED lifecycle."""

    def test_execute_active_to_suspended(self):
        subscription = _subscription()
        lifecycle = _lifecycle(subscription, _STATE.ACTIVE)
        transition = _transition(subscription, _STATE.ACTIVE, _STATE.SUSPENDED)

        result = _executor().execute(lifecycle, transition)

        assert result.state == _STATE.SUSPENDED


class TestExecuteSuspendedToActive:
    """Executing SUSPENDED -> ACTIVE produces an ACTIVE lifecycle."""

    def test_execute_suspended_to_active(self):
        subscription = _subscription()
        lifecycle = _lifecycle(subscription, _STATE.SUSPENDED)
        transition = _transition(subscription, _STATE.SUSPENDED, _STATE.ACTIVE)

        result = _executor().execute(lifecycle, transition)

        assert result.state == _STATE.ACTIVE


class TestExecuteActiveToUnregistered:
    """Executing ACTIVE -> UNREGISTERED produces an UNREGISTERED lifecycle."""

    def test_execute_active_to_unregistered(self):
        subscription = _subscription()
        lifecycle = _lifecycle(subscription, _STATE.ACTIVE)
        transition = _transition(subscription, _STATE.ACTIVE, _STATE.UNREGISTERED)

        result = _executor().execute(lifecycle, transition)

        assert result.state == _STATE.UNREGISTERED


class TestRejectNoneLifecycle:
    """A None lifecycle is rejected."""

    def test_reject_none_lifecycle(self):
        subscription = _subscription()
        transition = _transition(subscription, _STATE.REGISTERED, _STATE.ACTIVE)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutorError
        ):
            _executor().execute(None, transition)


class TestRejectNoneTransition:
    """A None transition is rejected."""

    def test_reject_none_transition(self):
        subscription = _subscription()
        lifecycle = _lifecycle(subscription, _STATE.REGISTERED)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutorError
        ):
            _executor().execute(lifecycle, None)


class TestRejectSubscriptionMismatch:
    """A lifecycle/transition subscription mismatch is rejected."""

    def test_reject_subscription_mismatch(self):
        lifecycle = _lifecycle(_subscription("one"), _STATE.REGISTERED)
        transition = _transition(_subscription("two"), _STATE.REGISTERED, _STATE.ACTIVE)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutorError
        ):
            _executor().execute(lifecycle, transition)


class TestRejectStateMismatch:
    """A lifecycle state that differs from transition.from_state is rejected."""

    def test_reject_state_mismatch(self):
        subscription = _subscription()
        lifecycle = _lifecycle(subscription, _STATE.SUSPENDED)
        transition = _transition(subscription, _STATE.REGISTERED, _STATE.ACTIVE)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutorError
        ):
            _executor().execute(lifecycle, transition)


class _CountingValidator:
    def __init__(self):
        self.calls = 0

    def validate(self, transition):
        self.calls += 1

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidator().validate(
            transition
        )


class _CountingBuilder:
    def __init__(self):
        self.calls = 0

    def build(self, subscription, state):
        self.calls += 1

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder().build(
            subscription,
            state,
        )


class TestValidatorInvokedExactlyOnce:
    """The injected validator is invoked exactly once per execution."""

    def test_validator_invoked_exactly_once(self):
        subscription = _subscription()
        lifecycle = _lifecycle(subscription, _STATE.REGISTERED)
        transition = _transition(subscription, _STATE.REGISTERED, _STATE.ACTIVE)

        validator = _CountingValidator()

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutor(
            validator,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder(),
        )

        executor.execute(lifecycle, transition)

        assert validator.calls == 1


class TestBuilderInvokedExactlyOnce:
    """The injected builder is invoked exactly once per execution."""

    def test_builder_invoked_exactly_once(self):
        subscription = _subscription()
        lifecycle = _lifecycle(subscription, _STATE.REGISTERED)
        transition = _transition(subscription, _STATE.REGISTERED, _STATE.ACTIVE)

        builder = _CountingBuilder()

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutor(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidator(),
            builder,
        )

        executor.execute(lifecycle, transition)

        assert builder.calls == 1
