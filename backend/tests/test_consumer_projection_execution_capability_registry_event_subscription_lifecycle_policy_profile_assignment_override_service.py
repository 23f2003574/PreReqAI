import dataclasses
from datetime import datetime, timezone
import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverride,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService,
)


def _build_profile(profile_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,
        profile_name=profile_id,
        description=f"Profile {profile_id}.",
        policy_identifiers=("policy-a",),
    )


def _build_profile_service(*profile_ids):
    svc = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()
    for profile_id in profile_ids:
        svc.register(_build_profile(profile_id))
    return svc


def _build_assignment(target_id, profile_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment(
        assignment_id=f"{target_id}::{profile_id}::1",
        target_id=target_id,
        profile_id=profile_id,
        assigned_at=datetime.now(timezone.utc),
    )


def _build_registry(*assignments):
    registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryService()
    for assignment in assignments:
        registry.register(assignment)
    return registry


def _build_override(override_id, target_id, profile_id, priority=1, active=True):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverride(
        override_id=override_id,
        target_id=target_id,
        profile_id=profile_id,
        priority=priority,
        active=active,
    )


class TestAddAndRemoveOverride:
    """Tests override registration and removal operations."""

    def test_add_override(self):
        profiles = _build_profile_service("profile-a", "profile-b")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideService(registry, profiles)

        override = _build_override("override-1", "target-1", "profile-a")
        service.add_override(override)

        overrides = service.list_overrides("target-1")
        assert len(overrides) == 1
        assert overrides[0] is override

    def test_remove_override(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideService(registry, profiles)

        override = _build_override("override-1", "target-1", "profile-a")
        service.add_override(override)
        service.remove_override("override-1")

        assert len(service.list_overrides("target-1")) == 0


class TestResolutionBehavior:
    """Tests highest priority selection, fallback, and multiple overrides."""

    def test_highest_priority_selected(self):
        profiles = _build_profile_service("profile-a", "profile-b")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideService(registry, profiles)

        # Register two active overrides for target-1 with different priorities
        service.add_override(_build_override("override-low", "target-1", "profile-a", priority=10))
        service.add_override(_build_override("override-high", "target-1", "profile-b", priority=20))

        result = service.resolve_effective("target-1")
        assert result.effective_profile_id == "profile-b"
        assert result.override_applied is True

    def test_deterministic_priority_tie_breaking(self):
        profiles = _build_profile_service("profile-a", "profile-b")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideService(registry, profiles)

        # Same priority, tie broken by override_id alphabetically (e.g. override-a vs override-b)
        service.add_override(_build_override("override-b", "target-1", "profile-b", priority=10))
        service.add_override(_build_override("override-a", "target-1", "profile-a", priority=10))

        result = service.resolve_effective("target-1")
        assert result.effective_profile_id == "profile-a"
        assert result.override_applied is True

    def test_fallback_to_assignment(self):
        profiles = _build_profile_service("profile-a", "profile-b")
        assignment = _build_assignment("target-1", "profile-a")
        registry = _build_registry(assignment)

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideService(registry, profiles)

        # Overrides exist but are inactive
        service.add_override(_build_override("override-1", "target-1", "profile-b", priority=10, active=False))

        result = service.resolve_effective("target-1")
        assert result.effective_profile_id == "profile-a"
        assert result.override_applied is False

    def test_fallback_to_none_when_no_assignment(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideService(registry, profiles)

        result = service.resolve_effective("target-1")
        assert result.effective_profile_id is None
        assert result.override_applied is False


class TestValidationRejections:
    """Tests validation rejections for inputs like blank values, unknown profiles, duplicates, negative priority."""

    def test_reject_blank_override_ids(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError):
            _build_override("   ", "target-1", "profile-a")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError):
            _build_override("override-1", "", "profile-a")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError):
            _build_override("override-1", "target-1", None)

    def test_reject_negative_priority(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError):
            _build_override("override-1", "target-1", "profile-a", priority=-5)

    def test_reject_unknown_profile(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideService(registry, profiles)

        override = _build_override("override-1", "target-1", "profile-unknown")
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError):
            service.add_override(override)

    def test_reject_duplicate_override_ids(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideService(registry, profiles)

        override1 = _build_override("override-1", "target-1", "profile-a")
        override2 = _build_override("override-1", "target-2", "profile-a")

        service.add_override(override1)
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError):
            service.add_override(override2)


class TestImmutableResults:
    """Tests result and override immutability."""

    def test_immutable_results(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideService(registry, profiles)

        override = _build_override("override-1", "target-1", "profile-a")
        service.add_override(override)

        result = service.resolve_effective("target-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.effective_profile_id = "new-profile"

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.override_applied = False

        with pytest.raises(dataclasses.FrozenInstanceError):
            override.priority = 100
