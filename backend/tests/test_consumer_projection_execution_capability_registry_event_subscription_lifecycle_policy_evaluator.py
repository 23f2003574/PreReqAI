import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluator,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluatorError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator,
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


def _transition(from_state, to_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder().build(
        _subscription(),
        from_state,
        to_state,
    )


def _policy(allowed_states, initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        allowed_states,
        initial_state,
    )


def _request(allowed_states, from_state, to_state):
    policy = _policy(
        allowed_states,
        allowed_states[0],
    )

    transition = _transition(from_state, to_state)

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder().build(
        policy,
        transition,
    )


def _evaluator():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluator(
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator(),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder(),
    )


class TestApproveWhenBothStatesAreAllowed:
    """A transition is approved when both states are allowed by the policy."""

    def test_approve_when_both_states_are_allowed(self):
        request = _request(
            (
                _STATE.REGISTERED,
                _STATE.ACTIVE,
            ),
            _STATE.REGISTERED,
            _STATE.ACTIVE,
        )

        result = _evaluator().evaluate(request)

        assert result.approved is True
        assert result.rejection_reason is None


class TestRejectWhenSourceStateNotAllowed:
    """A transition is rejected when the source state is not allowed by the policy."""

    def test_reject_when_source_state_not_allowed(self):
        request = _request(
            (
                _STATE.ACTIVE,
                _STATE.SUSPENDED,
            ),
            _STATE.REGISTERED,
            _STATE.SUSPENDED,
        )

        result = _evaluator().evaluate(request)

        assert result.approved is False
        assert result.rejection_reason == "Lifecycle state is not permitted by policy."


class TestRejectWhenDestinationStateNotAllowed:
    """A transition is rejected when the destination state is not allowed by the policy."""

    def test_reject_when_destination_state_not_allowed(self):
        request = _request(
            (
                _STATE.REGISTERED,
                _STATE.ACTIVE,
            ),
            _STATE.REGISTERED,
            _STATE.UNREGISTERED,
        )

        result = _evaluator().evaluate(request)

        assert result.approved is False
        assert result.rejection_reason == "Lifecycle state is not permitted by policy."


class TestRejectWhenBothStatesNotAllowed:
    """A transition is rejected when neither state is allowed by the policy."""

    def test_reject_when_both_states_not_allowed(self):
        request = _request(
            (
                _STATE.SUSPENDED,
            ),
            _STATE.REGISTERED,
            _STATE.ACTIVE,
        )

        result = _evaluator().evaluate(request)

        assert result.approved is False
        assert result.rejection_reason == "Lifecycle state is not permitted by policy."


class TestRejectNoneRequest:
    """A None request is rejected."""

    def test_reject_none_request(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluatorError
        ):
            _evaluator().evaluate(None)


class _CountingPolicyValidator:
    def __init__(self):
        self.calls = 0

    def validate(self, policy):
        self.calls += 1

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator().validate(
            policy
        )


class _CountingResultBuilder:
    def __init__(self):
        self.calls = 0

    def build(self, request, approved, rejection_reason=None):
        self.calls += 1

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder().build(
            request,
            approved,
            rejection_reason,
        )


class TestPolicyValidatorInvokedExactlyOnce:
    """The injected policy validator is invoked exactly once per evaluation."""

    def test_policy_validator_invoked_exactly_once(self):
        request = _request(
            (
                _STATE.REGISTERED,
                _STATE.ACTIVE,
            ),
            _STATE.REGISTERED,
            _STATE.ACTIVE,
        )

        policy_validator = _CountingPolicyValidator()

        evaluator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluator(
            policy_validator,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder(),
        )

        evaluator.evaluate(request)

        assert policy_validator.calls == 1


class TestResultBuilderInvokedExactlyOnce:
    """The injected result builder is invoked exactly once per evaluation."""

    def test_result_builder_invoked_exactly_once(self):
        request = _request(
            (
                _STATE.REGISTERED,
                _STATE.ACTIVE,
            ),
            _STATE.REGISTERED,
            _STATE.ACTIVE,
        )

        result_builder = _CountingResultBuilder()

        evaluator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluator(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator(),
            result_builder,
        )

        evaluator.evaluate(request)

        assert result_builder.calls == 1


class TestApprovedResultContainsNoRejectionReason:
    """An approved evaluation result carries no rejection reason."""

    def test_approved_result_contains_no_rejection_reason(self):
        request = _request(
            (
                _STATE.REGISTERED,
                _STATE.ACTIVE,
            ),
            _STATE.REGISTERED,
            _STATE.ACTIVE,
        )

        result = _evaluator().evaluate(request)

        assert result.rejection_reason is None


class TestRejectedResultContainsExpectedRejectionReason:
    """A rejected evaluation result carries the expected rejection reason."""

    def test_rejected_result_contains_expected_rejection_reason(self):
        request = _request(
            (
                _STATE.SUSPENDED,
            ),
            _STATE.REGISTERED,
            _STATE.ACTIVE,
        )

        result = _evaluator().evaluate(request)

        assert result.rejection_reason == "Lifecycle state is not permitted by policy."


class TestDeterministicEvaluation:
    """Evaluating the same request twice produces equal results."""

    def test_deterministic_evaluation(self):
        request = _request(
            (
                _STATE.REGISTERED,
                _STATE.ACTIVE,
            ),
            _STATE.REGISTERED,
            _STATE.ACTIVE,
        )

        evaluator = _evaluator()

        first = evaluator.evaluate(request)
        second = evaluator.evaluate(request)

        assert first == second
