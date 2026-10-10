import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultError,
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


def _request():
    policy = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (
            _STATE.REGISTERED,
            _STATE.ACTIVE,
            _STATE.SUSPENDED,
            _STATE.UNREGISTERED,
        ),
        _STATE.REGISTERED,
    )

    transition = _transition(_STATE.REGISTERED, _STATE.ACTIVE)

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder().build(
        policy,
        transition,
    )


class TestBuildApprovedResult:
    """An approved result can be built without a rejection reason."""

    def test_build_approved_result(self):
        request = _request()

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder().build(
            request,
            True,
        )

        assert result.approved is True
        assert result.rejection_reason is None


class TestBuildRejectedResult:
    """A rejected result can be built with a rejection reason."""

    def test_build_rejected_result(self):
        request = _request()

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder().build(
            request,
            False,
            "transition is not permitted",
        )

        assert result.approved is False
        assert result.rejection_reason == "transition is not permitted"


class TestRejectNoneRequest:
    """A None request is rejected."""

    def test_reject_none_request(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder().build(
                None,
                True,
            )


class TestRejectApprovedResultWithRejectionReason:
    """An approved result carrying a rejection reason is rejected."""

    def test_reject_approved_result_with_rejection_reason(self):
        request = _request()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder().build(
                request,
                True,
                "should not be present",
            )


class TestRejectRejectedResultWithoutRejectionReason:
    """A rejected result without a rejection reason is rejected."""

    def test_reject_rejected_result_without_rejection_reason(self):
        request = _request()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder().build(
                request,
                False,
            )


class TestPreserveRequestReference:
    """The result preserves the exact request reference passed in."""

    def test_preserve_request_reference(self):
        request = _request()

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder().build(
            request,
            True,
        )

        assert result.request is request


class TestImmutableResult:
    """A built result cannot have its fields reassigned."""

    def test_immutable_result(self):
        request = _request()

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder().build(
            request,
            True,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.approved = False


class TestDeterministicConstruction:
    """Building the same inputs twice produces equal, distinct results."""

    def test_deterministic_construction(self):
        request = _request()

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder()

        first = builder.build(
            request,
            False,
            "transition is not permitted",
        )
        second = builder.build(
            request,
            False,
            "transition is not permitted",
        )

        assert first == second
        assert first is not second
        assert dataclasses.is_dataclass(first)
        assert isinstance(
            first,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResult,
        )


class TestEqualityForIdenticalResults:
    """Results built from the same inputs compare equal."""

    def test_equality_for_identical_results(self):
        request = _request()

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder()

        first = builder.build(
            request,
            True,
        )
        second = builder.build(
            request,
            True,
        )

        assert first == second


class TestDifferentApprovalStatesProduceDifferentResults:
    """Results with different approval states do not compare equal."""

    def test_different_approval_states_produce_different_results(self):
        request = _request()

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder()

        first = builder.build(
            request,
            True,
        )
        second = builder.build(
            request,
            False,
            "transition is not permitted",
        )

        assert first != second
