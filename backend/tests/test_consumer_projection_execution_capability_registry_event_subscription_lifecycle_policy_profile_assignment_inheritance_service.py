import dataclasses
from datetime import datetime, timezone
import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritance,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceService,
)


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


class TestResolveEffective:
    """Tests resolving effective profile assignments with local override and inheritance."""

    def test_direct_assignment_overrides_inherited(self):
        # target-a has profile-a, target-b inherits from target-a but has local profile-b
        assignment_a = _build_assignment("target-a", "profile-a")
        assignment_b = _build_assignment("target-b", "profile-b")
        registry = _build_registry(assignment_a, assignment_b)

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceService(registry)
        service.inherit("target-b", "target-a")

        result = service.resolve_effective("target-b")
        assert result.effective_profile_id == "profile-b"
        assert result.inherited is False
        assert result.inheritance_chain == ()

    def test_inherit_from_parent(self):
        # target-a has profile-a, target-b inherits from target-a and has no local assignment
        assignment_a = _build_assignment("target-a", "profile-a")
        registry = _build_registry(assignment_a)

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceService(registry)
        service.inherit("target-b", "target-a")

        result = service.resolve_effective("target-b")
        assert result.effective_profile_id == "profile-a"
        assert result.inherited is True
        assert len(result.inheritance_chain) == 1
        link = result.inheritance_chain[0]
        assert link.target_id == "target-b"
        assert link.parent_target_id == "target-a"
        assert link.inherited_profile_id == "profile-a"
        assert link.inheritance_depth == 1

    def test_multi_level_inheritance(self):
        # target-a has profile-a
        # target-b inherits from target-a (no local assignment)
        # target-c inherits from target-b (no local assignment)
        assignment_a = _build_assignment("target-a", "profile-a")
        registry = _build_registry(assignment_a)

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceService(registry)
        service.inherit("target-b", "target-a")
        service.inherit("target-c", "target-b")

        result = service.resolve_effective("target-c")
        assert result.effective_profile_id == "profile-a"
        assert result.inherited is True
        assert len(result.inheritance_chain) == 2

        # Link 0: target-c -> target-b, distance to target-a is 2
        link0 = result.inheritance_chain[0]
        assert link0.target_id == "target-c"
        assert link0.parent_target_id == "target-b"
        assert link0.inherited_profile_id == "profile-a"
        assert link0.inheritance_depth == 2

        # Link 1: target-b -> target-a, distance to target-a is 1
        link1 = result.inheritance_chain[1]
        assert link1.target_id == "target-b"
        assert link1.parent_target_id == "target-a"
        assert link1.inherited_profile_id == "profile-a"
        assert link1.inheritance_depth == 1

    def test_break_inheritance(self):
        # target-a has profile-a, target-b inherits from target-a (no local assignment)
        assignment_a = _build_assignment("target-a", "profile-a")
        registry = _build_registry(assignment_a)

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceService(registry)
        service.inherit("target-b", "target-a")

        assert service.resolve_effective("target-b").effective_profile_id == "profile-a"

        service.break_inheritance("target-b")
        assert service.resolve_effective("target-b").effective_profile_id is None
        assert service.resolve_effective("target-b").inheritance_chain == ()


class TestValidationAndCycleDetection:
    """Tests rejections of cycles, depth limits, and bad inputs."""

    def test_cycle_detection_direct(self):
        assignment_a = _build_assignment("target-a", "profile-a")
        registry = _build_registry(assignment_a)

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceService(registry)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError):
            # target-a trying to inherit from target-a
            service.inherit("target-a", "target-a")

    def test_cycle_detection_indirect(self):
        assignment_a = _build_assignment("target-a", "profile-a")
        registry = _build_registry(assignment_a)

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceService(registry)
        service.inherit("target-b", "target-a")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError):
            # target-a inherits from target-b
            service.inherit("target-a", "target-b")

    def test_depth_limit(self):
        assignment_a = _build_assignment("target-a", "profile-a")
        registry = _build_registry(assignment_a)

        # Set max_depth to 2
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceService(registry, max_depth=2)
        service.inherit("target-b", "target-a")
        service.inherit("target-c", "target-b")  # This path has depth 2

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError):
            # This would make the path depth 3, exceeding max_depth=2
            service.inherit("target-d", "target-c")

    def test_missing_parent_target(self):
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceService(registry)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError):
            # parent target-a does not exist in registry or inheritance structure
            service.inherit("target-b", "target-a")

    def test_none_or_blank_ids(self):
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceService(registry)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError):
            service.inherit("   ", "target-a")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError):
            service.inherit("target-b", None)


class TestImmutableResults:
    """Tests that result models are frozen/immutable."""

    def test_immutable_results(self):
        assignment_a = _build_assignment("target-a", "profile-a")
        registry = _build_registry(assignment_a)

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceService(registry)
        service.inherit("target-b", "target-a")

        result = service.resolve_effective("target-b")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.effective_profile_id = "new-profile"

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.inherited = False

        if len(result.inheritance_chain) > 0:
            with pytest.raises(dataclasses.FrozenInstanceError):
                result.inheritance_chain[0].target_id = "other-target"
