import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraint,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService,
)


class FakeClock:
    def __init__(self, now):
        self.current = now

    def now(self):
        return self.current


def _build_profile(profile_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,
        profile_name=profile_id,
        description=f"Profile {profile_id}.",
        policy_identifiers=(f"policy-{profile_id}",),
    )


def _build_context(profile_ids=("profile-a",)):
    profile_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()

    for profile_id in profile_ids:
        profile_service.register(_build_profile(profile_id))

    binding_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingService(profile_service)

    activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(
        binding_service,
        FakeClock(datetime.now(timezone.utc)),
    )

    constraint_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintService(
        binding_service,
        activation_service,
    )

    return constraint_service, binding_service, activation_service


def _constraint(constraint_id, binding_id, constraint_type, key, value=None):
    constraint_value = {"key": key} if value is None else {"key": key, "value": value}

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraint(
        constraint_id=constraint_id,
        binding_id=binding_id,
        constraint_type=constraint_type,
        constraint_value=constraint_value,
    )


class TestAddRemoveConstraint:
    def test_add_and_remove_constraint(self):
        constraint_service, binding_service, _ = _build_context()

        binding = binding_service.bind("profile-a", "capability-a")
        constraint = _constraint("constraint-1", binding.binding_id, "present", "region")

        constraint_service.add_constraint(constraint)
        assert constraint_service.constraints(binding.binding_id) == (constraint,)

        constraint_service.remove_constraint("constraint-1")
        assert constraint_service.constraints(binding.binding_id) == ()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError):
            constraint_service.remove_constraint("constraint-1")


class TestEvaluateSuccess:
    def test_evaluate_success(self):
        constraint_service, binding_service, activation_service = _build_context()

        binding = binding_service.bind("profile-a", "capability-a")
        activation_service.activate(binding.binding_id)

        constraint_service.add_constraint(_constraint("constraint-1", binding.binding_id, "equals", "region", "us-east"))
        constraint_service.add_constraint(_constraint("constraint-2", binding.binding_id, "min", "capacity", 10))

        result = constraint_service.evaluate(binding.binding_id, {"region": "us-east", "capacity": 20})

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintResult)
        assert result.satisfied is True
        assert result.failed_constraints == ()


class TestEvaluateFailure:
    def test_evaluate_failure(self):
        constraint_service, binding_service, activation_service = _build_context()

        binding = binding_service.bind("profile-a", "capability-a")
        activation_service.activate(binding.binding_id)

        constraint = _constraint("constraint-1", binding.binding_id, "equals", "region", "us-east")
        constraint_service.add_constraint(constraint)

        result = constraint_service.evaluate(binding.binding_id, {"region": "eu-west"})

        assert result.satisfied is False
        assert result.failed_constraints == (constraint,)

    def test_evaluate_inactive_binding_skipped(self):
        constraint_service, binding_service, _ = _build_context()

        binding = binding_service.bind("profile-a", "capability-a")
        constraint_service.add_constraint(_constraint("constraint-1", binding.binding_id, "present", "region"))

        result = constraint_service.evaluate(binding.binding_id, {"region": "us-east"})

        assert result.satisfied is False
        assert result.failed_constraints == ()


class TestMultipleConstraints:
    def test_multiple_constraints_all_evaluated(self):
        constraint_service, binding_service, activation_service = _build_context()

        binding = binding_service.bind("profile-a", "capability-a")
        activation_service.activate(binding.binding_id)

        first = _constraint("constraint-1", binding.binding_id, "equals", "region", "us-east")
        second = _constraint("constraint-2", binding.binding_id, "max", "latency_ms", 100)
        third = _constraint("constraint-3", binding.binding_id, "present", "tenant")

        constraint_service.add_constraint(first)
        constraint_service.add_constraint(second)
        constraint_service.add_constraint(third)

        result = constraint_service.evaluate(binding.binding_id, {"region": "eu-west", "latency_ms": 500})

        assert result.satisfied is False
        assert result.failed_constraints == (first, second, third)


class TestDuplicateRejection:
    def test_reject_duplicate_constraint_id(self):
        constraint_service, binding_service, _ = _build_context()

        binding = binding_service.bind("profile-a", "capability-a")
        constraint_service.add_constraint(_constraint("constraint-1", binding.binding_id, "present", "region"))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError):
            constraint_service.add_constraint(_constraint("constraint-1", binding.binding_id, "present", "tenant"))

    def test_reject_invalid_constraint_type(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError):
            _constraint("constraint-1", "binding-1", "not-a-real-type", "region")

    def test_reject_unknown_binding(self):
        constraint_service, _, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError):
            constraint_service.add_constraint(_constraint("constraint-1", "binding-missing", "present", "region"))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError):
            constraint_service.evaluate("binding-missing", {})

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError):
            constraint_service.constraints("binding-missing")

    def test_reject_blank_ids(self):
        constraint_service, _, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError):
            constraint_service.evaluate("   ", {})

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError):
            constraint_service.remove_constraint(None)

    def test_reject_none_constraint(self):
        constraint_service, _, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError):
            constraint_service.add_constraint(None)


class TestImmutableResults:
    def test_immutable_result(self):
        constraint_service, binding_service, activation_service = _build_context()

        binding = binding_service.bind("profile-a", "capability-a")
        activation_service.activate(binding.binding_id)

        result = constraint_service.evaluate(binding.binding_id, {})

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.satisfied = True
