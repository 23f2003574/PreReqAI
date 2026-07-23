import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder,
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


def _transition(from_state, to_state, name="subscription"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder().build(
        _subscription(name),
        from_state,
        to_state,
    )


def _policy(allowed_states, initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        allowed_states,
        initial_state,
    )


def _default_policy():
    return _policy(
        (
            _STATE.REGISTERED,
            _STATE.ACTIVE,
            _STATE.SUSPENDED,
            _STATE.UNREGISTERED,
        ),
        _STATE.REGISTERED,
    )


class TestBuildValidEvaluationRequest:
    """A valid evaluation request can be built from a policy and a transition."""

    def test_build_valid_evaluation_request(self):
        policy = _default_policy()
        transition = _transition(_STATE.REGISTERED, _STATE.ACTIVE)

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder().build(
            policy,
            transition,
        )

        assert isinstance(
            request,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequest,
        )


class TestPreservePolicyReference:
    """The request preserves the exact policy reference passed in."""

    def test_preserve_policy_reference(self):
        policy = _default_policy()
        transition = _transition(_STATE.REGISTERED, _STATE.ACTIVE)

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder().build(
            policy,
            transition,
        )

        assert request.policy is policy


class TestPreserveTransitionReference:
    """The request preserves the exact transition reference passed in."""

    def test_preserve_transition_reference(self):
        policy = _default_policy()
        transition = _transition(_STATE.REGISTERED, _STATE.ACTIVE)

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder().build(
            policy,
            transition,
        )

        assert request.transition is transition


class TestRejectNonePolicy:
    """A None policy is rejected."""

    def test_reject_none_policy(self):
        transition = _transition(_STATE.REGISTERED, _STATE.ACTIVE)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder().build(
                None,
                transition,
            )


class TestRejectNoneTransition:
    """A None transition is rejected."""

    def test_reject_none_transition(self):
        policy = _default_policy()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder().build(
                policy,
                None,
            )


class TestImmutableEvaluationRequest:
    """A built evaluation request cannot have its fields reassigned."""

    def test_immutable_evaluation_request(self):
        policy = _default_policy()
        transition = _transition(_STATE.REGISTERED, _STATE.ACTIVE)

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder().build(
            policy,
            transition,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            request.policy = _default_policy()


class TestDeterministicConstruction:
    """Building the same inputs twice produces equal, distinct requests."""

    def test_deterministic_construction(self):
        policy = _default_policy()
        transition = _transition(_STATE.REGISTERED, _STATE.ACTIVE)

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder()

        first = builder.build(
            policy,
            transition,
        )
        second = builder.build(
            policy,
            transition,
        )

        assert first == second
        assert first is not second
        assert dataclasses.is_dataclass(first)
        assert isinstance(
            first,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequest,
        )


class TestEqualityForIdenticalRequests:
    """Requests built from the same policy and transition compare equal."""

    def test_equality_for_identical_requests(self):
        policy = _default_policy()
        transition = _transition(_STATE.REGISTERED, _STATE.ACTIVE)

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder()

        first = builder.build(
            policy,
            transition,
        )
        second = builder.build(
            policy,
            transition,
        )

        assert first == second


class TestDifferentPoliciesProduceDifferentRequests:
    """Requests built with different policies do not compare equal."""

    def test_different_policies_produce_different_requests(self):
        transition = _transition(_STATE.REGISTERED, _STATE.ACTIVE)

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder()

        first = builder.build(
            _default_policy(),
            transition,
        )
        second = builder.build(
            _policy(
                (_STATE.REGISTERED,),
                _STATE.REGISTERED,
            ),
            transition,
        )

        assert first != second


class TestDifferentTransitionsProduceDifferentRequests:
    """Requests built with different transitions do not compare equal."""

    def test_different_transitions_produce_different_requests(self):
        policy = _default_policy()

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder()

        first = builder.build(
            policy,
            _transition(_STATE.REGISTERED, _STATE.ACTIVE),
        )
        second = builder.build(
            policy,
            _transition(_STATE.REGISTERED, _STATE.UNREGISTERED),
        )

        assert first != second
