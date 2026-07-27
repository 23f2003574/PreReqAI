import dataclasses
from datetime import datetime, timezone
import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScope,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileScopedAssignment,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeService,
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


def _build_scope(scope_id, scope_type="environment", scope_value="production"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScope(
        scope_id=scope_id,
        scope_type=scope_type,
        scope_value=scope_value,
    )


class TestAddAndRemoveScopedAssignment:
    """Tests scoped profile assignments (assign and unassign operations)."""

    def test_assign_scoped_profile(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeService(registry, profiles)

        scope = _build_scope("scope-1")
        service.assign("target-1", "profile-a", scope)

        assigned = service.list("target-1")
        assert len(assigned) == 1
        assert assigned[0].profile_id == "profile-a"
        assert assigned[0].scope == scope

    def test_remove_scoped_assignment(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeService(registry, profiles)

        scope = _build_scope("scope-1")
        service.assign("target-1", "profile-a", scope)
        service.unassign("target-1", scope)

        assert len(service.list("target-1")) == 0


class TestResolutionAndFallback:
    """Tests scoped assignment resolution and global fallback behavior."""

    def test_resolve_scoped_assignment(self):
        profiles = _build_profile_service("profile-a", "profile-b")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeService(registry, profiles)

        scope1 = _build_scope("scope-1")
        scope2 = _build_scope("scope-2")

        service.assign("target-1", "profile-a", scope1)
        service.assign("target-1", "profile-b", scope2)

        assert service.resolve("target-1", scope1) == "profile-a"
        assert service.resolve("target-1", scope2) == "profile-b"

    def test_fallback_to_global_assignment(self):
        profiles = _build_profile_service("profile-a", "profile-b")
        assignment = _build_assignment("target-1", "profile-b")
        registry = _build_registry(assignment)
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeService(registry, profiles)

        # No scoped assignment matches
        scope = _build_scope("scope-1")
        assert service.resolve("target-1", scope) == "profile-b"

    def test_replace_scoped_assignment(self):
        profiles = _build_profile_service("profile-a", "profile-b")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeService(registry, profiles)

        scope = _build_scope("scope-1")
        service.assign("target-1", "profile-a", scope)

        # Assign different profile ID to the same scope replaces the assignment
        service.assign("target-1", "profile-b", scope)

        assert service.resolve("target-1", scope) == "profile-b"
        assert len(service.list("target-1")) == 1


class TestValidationRejections:
    """Tests validation rejections for blank/None inputs, invalid scopes, duplicate assignments, unknown profiles."""

    def test_reject_blank_or_invalid_fields(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError):
            _build_scope("   ", "env", "prod")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError):
            _build_scope("scope-1", "", "prod")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError):
            _build_scope("scope-1", "env", None)

    def test_reject_duplicate_scope_assignment(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeService(registry, profiles)

        scope = _build_scope("scope-1")
        service.assign("target-1", "profile-a", scope)

        # Exact duplicate target-id, profile-id, scope-id assignment
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError):
            service.assign("target-1", "profile-a", scope)

    def test_reject_unknown_profile(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeService(registry, profiles)

        scope = _build_scope("scope-1")
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError):
            service.assign("target-1", "profile-unknown", scope)


class TestImmutableAssignments:
    """Tests immutability constraints of scope and assignment models."""

    def test_immutable_assignments(self):
        profiles = _build_profile_service("profile-a")
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeService(registry, profiles)

        scope = _build_scope("scope-1")
        service.assign("target-1", "profile-a", scope)

        assigned = service.list("target-1")[0]

        with pytest.raises(dataclasses.FrozenInstanceError):
            assigned.target_id = "other-target"

        with pytest.raises(dataclasses.FrozenInstanceError):
            assigned.scope.scope_id = "other-scope"
