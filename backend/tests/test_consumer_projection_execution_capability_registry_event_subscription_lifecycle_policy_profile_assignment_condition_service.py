import dataclasses
from datetime import datetime, timezone
import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentCondition,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionService,
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


def _build_condition(condition_id, target_id, profile_id, expression, priority=1):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentCondition(
        condition_id=condition_id,
        target_id=target_id,
        profile_id=profile_id,
        expression=expression,
        priority=priority,
    )


class TestAddAndRemoveCondition:
    """Tests condition registration and removal operations."""

    def test_register_condition(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionService(registry, profiles)

        condition = _build_condition("cond-1", "target-1", "profile-a", "env == 'prod'")
        service.register(condition)

        conds = service.list("target-1")
        assert len(conds) == 1
        assert conds[0] is condition

    def test_remove_condition(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionService(registry, profiles)

        condition = _build_condition("cond-1", "target-1", "profile-a", "env == 'prod'")
        service.register(condition)
        service.remove("cond-1")

        assert len(service.list("target-1")) == 0


class TestEvaluationBehavior:
    """Tests priority ordering, condition selection, and fallback."""

    def test_matching_condition_selected(self):
        profiles = _build_profile_service("profile-a", "profile-b")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionService(registry, profiles)

        service.register(_build_condition("cond-1", "target-1", "profile-a", "env == 'prod'", priority=10))

        result = service.evaluate("target-1", {"env": "prod"})
        assert result.matched is True
        assert result.selected_profile_id == "profile-a"

    def test_priority_ordering(self):
        profiles = _build_profile_service("profile-a", "profile-b")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionService(registry, profiles)

        # Both match, but cond-high should be evaluated first because of priority
        service.register(_build_condition("cond-low", "target-1", "profile-a", "env == 'prod'", priority=10))
        service.register(_build_condition("cond-high", "target-1", "profile-b", "env == 'prod'", priority=20))

        result = service.evaluate("target-1", {"env": "prod"})
        assert result.matched is True
        assert result.selected_profile_id == "profile-b"

    def test_fallback_behavior(self):
        profiles = _build_profile_service("profile-a", "profile-b")
        assignment = _build_assignment("target-1", "profile-b")
        registry = _build_registry(assignment)
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionService(registry, profiles)

        # Register condition but context doesn't match
        service.register(_build_condition("cond-1", "target-1", "profile-a", "env == 'prod'", priority=10))

        result = service.evaluate("target-1", {"env": "dev"})
        assert result.matched is False
        assert result.selected_profile_id == "profile-b"


class TestValidationRejections:
    """Tests validation rejections: duplicate condition IDs, duplicate priorities, blank fields, invalid expressions."""

    def test_reject_blank_or_invalid_fields(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError):
            _build_condition("   ", "target-1", "profile-a", "env == 'prod'")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError):
            _build_condition("cond-1", "", "profile-a", "env == 'prod'")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError):
            _build_condition("cond-1", "target-1", None, "env == 'prod'")

    def test_reject_invalid_expression(self):
        # Invalid python expression syntax
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError):
            _build_condition("cond-1", "target-1", "profile-a", "env == ")

    def test_reject_duplicate_condition_id(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionService(registry, profiles)

        cond1 = _build_condition("cond-1", "target-1", "profile-a", "env == 'prod'")
        cond2 = _build_condition("cond-1", "target-2", "profile-a", "env == 'prod'")

        service.register(cond1)
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError):
            service.register(cond2)

    def test_reject_duplicate_priorities_for_same_target(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionService(registry, profiles)

        cond1 = _build_condition("cond-1", "target-1", "profile-a", "env == 'prod'", priority=10)
        cond2 = _build_condition("cond-2", "target-1", "profile-a", "env == 'dev'", priority=10)

        service.register(cond1)
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError):
            service.register(cond2)

    def test_allow_same_priorities_for_different_targets(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionService(registry, profiles)

        cond1 = _build_condition("cond-1", "target-1", "profile-a", "env == 'prod'", priority=10)
        cond2 = _build_condition("cond-2", "target-2", "profile-a", "env == 'dev'", priority=10)

        service.register(cond1)
        service.register(cond2)  # Should succeed since targets are different


class TestImmutableResults:
    """Tests immutability of result objects."""

    def test_immutable_results(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionService(registry, profiles)

        service.register(_build_condition("cond-1", "target-1", "profile-a", "env == 'prod'"))

        result = service.evaluate("target-1", {"env": "prod"})

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.matched = False

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.selected_profile_id = "other-profile"
