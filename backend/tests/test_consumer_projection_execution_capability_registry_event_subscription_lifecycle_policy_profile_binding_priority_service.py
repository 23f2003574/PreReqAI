import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriority,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityService,
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


def _build_context(profile_ids=("profile-a", "profile-b", "profile-c")):
    profile_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()

    for profile_id in profile_ids:
        profile_service.register(_build_profile(profile_id))

    binding_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingService(profile_service)

    activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(
        binding_service,
        FakeClock(datetime.now(timezone.utc)),
    )

    priority_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityService(
        binding_service,
        activation_service,
    )

    return priority_service, binding_service, activation_service


class TestAssignPriority:
    def test_assign_priority(self):
        priority_service, binding_service, _ = _build_context()

        binding = binding_service.bind("profile-a", "capability-a")
        priority_service.set_priority(binding.binding_id, 5)

        assert priority_service.highest_priority(binding.binding_id) == 5


class TestHighestPriorityResolution:
    def test_highest_priority_resolution(self):
        priority_service, binding_service, activation_service = _build_context()

        low = binding_service.bind("profile-a", "capability-a")
        high = binding_service.bind("profile-b", "capability-a")

        activation_service.activate(low.binding_id)
        activation_service.activate(high.binding_id)

        priority_service.set_priority(low.binding_id, 1)
        priority_service.set_priority(high.binding_id, 10)

        result = priority_service.resolve_highest_priority("capability-a")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityResult)
        assert result.selected_binding == high
        assert result.evaluated_bindings == (high, low)


class TestEqualPriorityOrdering:
    def test_equal_priority_ordering_is_stable_by_binding_id(self):
        priority_service, binding_service, activation_service = _build_context()

        first = binding_service.bind("profile-a", "capability-a")
        second = binding_service.bind("profile-b", "capability-a")

        activation_service.activate(first.binding_id)
        activation_service.activate(second.binding_id)

        priority_service.set_priority(first.binding_id, 5)
        priority_service.set_priority(second.binding_id, 5)

        ordered = priority_service.ordered_bindings("capability-a")

        assert ordered == tuple(sorted([first, second], key=lambda b: b.binding_id))


class TestInactiveBindingIgnored:
    def test_inactive_binding_ignored(self):
        priority_service, binding_service, activation_service = _build_context()

        active = binding_service.bind("profile-a", "capability-a")
        inactive = binding_service.bind("profile-b", "capability-a")

        activation_service.activate(active.binding_id)
        priority_service.set_priority(inactive.binding_id, 100)

        result = priority_service.resolve_highest_priority("capability-a")

        assert result.selected_binding == active
        assert inactive not in result.evaluated_bindings


class TestPriorityUpdate:
    def test_priority_update(self):
        priority_service, binding_service, activation_service = _build_context()

        binding = binding_service.bind("profile-a", "capability-a")
        activation_service.activate(binding.binding_id)

        priority_service.set_priority(binding.binding_id, 1)
        assert priority_service.highest_priority(binding.binding_id) == 1

        priority_service.set_priority(binding.binding_id, 9)
        assert priority_service.highest_priority(binding.binding_id) == 9


class TestInvalidPriorityRejection:
    def test_reject_negative_priority(self):
        priority_service, binding_service, _ = _build_context()

        binding = binding_service.bind("profile-a", "capability-a")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError):
            priority_service.set_priority(binding.binding_id, -1)

    def test_reject_none_priority(self):
        priority_service, binding_service, _ = _build_context()

        binding = binding_service.bind("profile-a", "capability-a")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError):
            priority_service.set_priority(binding.binding_id, None)

    def test_reject_unknown_binding(self):
        priority_service, _, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError):
            priority_service.set_priority("binding-missing", 1)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError):
            priority_service.highest_priority("binding-missing")

    def test_reject_blank_ids(self):
        priority_service, _, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError):
            priority_service.set_priority("   ", 1)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError):
            priority_service.ordered_bindings(None)

    def test_reject_negative_priority_at_construction(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriority(
                binding_id="binding-1",
                priority=-5,
            )


class TestImmutableResults:
    def test_immutable_result(self):
        priority_service, binding_service, activation_service = _build_context()

        binding = binding_service.bind("profile-a", "capability-a")
        activation_service.activate(binding.binding_id)

        result = priority_service.resolve_highest_priority("capability-a")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.selected_binding = None
