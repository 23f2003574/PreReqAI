import dataclasses

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState,
)


class FakeClock:
    def __init__(self, now):
        self.current = now

    def now(self):
        return self.current

    def advance(self, delta):
        self.current = self.current + delta


def _build_binding(binding_id="binding-1"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id="profile-a",
        capability_id="capability-a",
        created_at=datetime.now(timezone.utc),
    )


def _build_context(binding_id="binding-1", now=None):
    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()
    binding_registry.register(_build_binding(binding_id))

    clock = FakeClock(now if now is not None else datetime.now(timezone.utc))

    service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(
        binding_registry,
        clock,
    )

    return service, binding_registry, clock


class TestActivateBinding:
    def test_activate_binding(self):
        service, _, clock = _build_context()

        result = service.activate("binding-1")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationResult)
        assert result.binding_id == "binding-1"
        assert result.previous_state == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.INACTIVE
        assert result.current_state == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE
        assert result.activated_at == clock.now()


class TestDeactivateBinding:
    def test_deactivate_binding(self):
        service, _, _ = _build_context()

        service.activate("binding-1")
        result = service.deactivate("binding-1")

        assert result.previous_state == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE
        assert result.current_state == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.INACTIVE
        assert result.activated_at is None
        assert service.state("binding-1") == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.INACTIVE


class TestScheduleActivation:
    def test_schedule_activation(self):
        base = datetime.now(timezone.utc)
        service, _, clock = _build_context(now=base)

        activation_time = base + timedelta(hours=1)
        result = service.schedule("binding-1", activation_time)

        assert result.current_state == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.SCHEDULED
        assert result.activated_at == activation_time
        assert service.state("binding-1") == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.SCHEDULED

        clock.advance(timedelta(hours=2))

        assert service.state("binding-1") == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE


class TestStateLookup:
    def test_state_lookup_default_inactive(self):
        service, _, _ = _build_context()

        assert service.state("binding-1") == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.INACTIVE

    def test_state_lookup_after_activation(self):
        service, _, _ = _build_context()

        service.activate("binding-1")

        assert service.state("binding-1") == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE


class TestIdempotentActivation:
    def test_idempotent_activation(self):
        service, _, clock = _build_context()

        first = service.activate("binding-1")
        clock.advance(timedelta(hours=1))
        second = service.activate("binding-1")

        assert first.activated_at == second.activated_at
        assert second.previous_state == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE
        assert second.current_state == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE

    def test_idempotent_deactivation(self):
        service, _, _ = _build_context()

        first = service.deactivate("binding-1")
        second = service.deactivate("binding-1")

        assert first.current_state == second.current_state == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.INACTIVE


class TestInvalidTransitionRejection:
    def test_reject_schedule_while_active(self):
        base = datetime.now(timezone.utc)
        service, _, clock = _build_context(now=base)

        service.activate("binding-1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError):
            service.schedule("binding-1", base + timedelta(hours=1))

    def test_reject_activation_time_in_the_past(self):
        base = datetime.now(timezone.utc)
        service, _, _ = _build_context(now=base)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError):
            service.schedule("binding-1", base - timedelta(hours=1))

    def test_reject_none_activation_time(self):
        service, _, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError):
            service.schedule("binding-1", None)

    def test_reject_unknown_binding(self):
        service, _, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError):
            service.activate("binding-missing")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError):
            service.deactivate("binding-missing")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError):
            service.state("binding-missing")

    def test_reject_blank_ids(self):
        service, _, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError):
            service.activate("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError):
            service.activate(None)


class TestImmutableActivationResult:
    def test_immutable_result(self):
        service, _, _ = _build_context()

        result = service.activate("binding-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.current_state = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.INACTIVE
