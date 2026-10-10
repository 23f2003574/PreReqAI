import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
)


_STATE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState


def _policy(allowed_states, initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy(
        allowed_states=allowed_states,
        initial_state=initial_state,
    )


class TestValidateSingleAllowedState:
    """A policy with one allowed state passes validation without raising."""

    def test_validate_single_allowed_state(self):
        policy = _policy(
            (_STATE.REGISTERED,),
            _STATE.REGISTERED,
        )

        assert (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator().validate(
                policy
            )
            is None
        )


class TestValidateMultipleAllowedStates:
    """A policy with multiple allowed states passes validation without raising."""

    def test_validate_multiple_allowed_states(self):
        policy = _policy(
            (
                _STATE.REGISTERED,
                _STATE.ACTIVE,
                _STATE.SUSPENDED,
                _STATE.UNREGISTERED,
            ),
            _STATE.ACTIVE,
        )

        assert (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator().validate(
                policy
            )
            is None
        )


class TestRejectNonePolicy:
    """A None policy is rejected."""

    def test_reject_none_policy(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidationError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator().validate(
                None
            )


class TestRejectEmptyAllowedStates:
    """A policy with empty allowed states is rejected."""

    def test_reject_empty_allowed_states(self):
        policy = _policy(
            (),
            _STATE.REGISTERED,
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidationError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator().validate(
                policy
            )


class TestRejectDuplicateAllowedStates:
    """A policy with duplicate allowed states is rejected."""

    def test_reject_duplicate_allowed_states(self):
        policy = _policy(
            (
                _STATE.REGISTERED,
                _STATE.REGISTERED,
            ),
            _STATE.REGISTERED,
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidationError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator().validate(
                policy
            )


class TestRejectInvalidLifecycleStateType:
    """A policy with a non-lifecycle-state value among allowed states is rejected."""

    def test_reject_invalid_lifecycle_state_type(self):
        policy = _policy(
            (
                _STATE.REGISTERED,
                "not-a-lifecycle-state",
            ),
            _STATE.REGISTERED,
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidationError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator().validate(
                policy
            )


class TestRejectMissingInitialState:
    """A policy with a missing initial state is rejected."""

    def test_reject_missing_initial_state(self):
        policy = _policy(
            (_STATE.REGISTERED,),
            None,
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidationError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator().validate(
                policy
            )


class TestRejectInitialStateOutsideAllowedStates:
    """A policy whose initial state is absent from the allowed states is rejected."""

    def test_reject_initial_state_outside_allowed_states(self):
        policy = _policy(
            (
                _STATE.REGISTERED,
                _STATE.ACTIVE,
            ),
            _STATE.SUSPENDED,
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidationError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator().validate(
                policy
            )


class TestPreservePolicyContents:
    """Validation does not alter the policy's allowed states or initial state."""

    def test_preserve_policy_contents(self):
        allowed_states = (
            _STATE.REGISTERED,
            _STATE.ACTIVE,
        )

        policy = _policy(
            allowed_states,
            _STATE.ACTIVE,
        )

        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator().validate(
            policy
        )

        assert policy.allowed_states == allowed_states
        assert policy.initial_state == _STATE.ACTIVE


class TestDeterministicValidation:
    """Validating the same policy twice produces the same outcome."""

    def test_deterministic_validation(self):
        policy = _policy(
            (
                _STATE.REGISTERED,
                _STATE.ACTIVE,
            ),
            _STATE.ACTIVE,
        )

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator()

        assert validator.validate(policy) is None
        assert validator.validate(policy) is None
