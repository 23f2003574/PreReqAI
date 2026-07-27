import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResultError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionSource,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolverError,
)


def _build_assignment(target_id, profile_id, sequence=1):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment(
        assignment_id=f"{target_id}::{profile_id}::{sequence}",

        target_id=target_id,

        profile_id=profile_id,

        assigned_at=datetime.now(timezone.utc),
    )


def _build_registry(*target_profile_pairs):
    registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryService()

    for i, (target_id, profile_id) in enumerate(target_profile_pairs, start=1):

        registry.register(
            _build_assignment(target_id, profile_id, sequence=i)
        )

    return registry


class TestResolveExistingAssignment:
    """An active assignment is found when a registered target ID is resolved."""

    def test_resolve_existing_assignment(self):
        registry = _build_registry(("target-1", "profile-a"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolver(
            registry
        )

        result = resolver.resolve("target-1")

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResult,
        )
        assert result.resolved is True
        assert result.target_id == "target-1"
        assert result.assignment is registry.find("target-1")
        assert result.resolution_source == (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionSource.REGISTRY
        )


class TestResolveMissingAssignment:
    """A target ID with no active assignment and no default resolves unsuccessfully."""

    def test_resolve_missing_assignment(self):
        registry = _build_registry(("target-1", "profile-a"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolver(
            registry
        )

        result = resolver.resolve("target-does-not-exist")

        assert result.resolved is False
        assert result.target_id == "target-does-not-exist"
        assert result.assignment is None
        assert result.resolution_source is None

    def test_resolve_missing_uses_default(self):
        registry = _build_registry(("target-1", "profile-a"))
        default_assignment = _build_assignment("target-default", "profile-default")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolver(
            registry,

            default_assignment=default_assignment,
        )

        result = resolver.resolve("target-does-not-exist")

        assert result.resolved is True
        assert result.assignment is default_assignment
        assert result.resolution_source == (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionSource.DEFAULT
        )


class TestResolveOrRaiseSuccess:
    """resolve_or_raise() returns the resolved assignment directly."""

    def test_resolve_or_raise_success(self):
        registry = _build_registry(("target-1", "profile-a"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolver(
            registry
        )

        resolved = resolver.resolve_or_raise("target-1")

        assert resolved is registry.find("target-1")


class TestResolveOrRaiseFailure:
    """resolve_or_raise() raises when no assignment can be resolved."""

    def test_resolve_or_raise_failure(self):
        registry = _build_registry(("target-1", "profile-a"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolver(
            registry
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolverError
        ):
            resolver.resolve_or_raise("target-does-not-exist")


class TestCanResolveTrue:
    """can_resolve() reports True for a target ID with an active assignment."""

    def test_can_resolve_true(self):
        registry = _build_registry(("target-1", "profile-a"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolver(
            registry
        )

        assert resolver.can_resolve("target-1") is True


class TestCanResolveFalse:
    """can_resolve() reports False for a target ID with no active assignment."""

    def test_can_resolve_false(self):
        registry = _build_registry(("target-1", "profile-a"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolver(
            registry
        )

        assert resolver.can_resolve("target-does-not-exist") is False


class TestImmutableResolutionResult:
    """Resolution results cannot have their fields reassigned."""

    def test_immutable_result(self):
        registry = _build_registry(("target-1", "profile-a"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolver(
            registry
        )

        result = resolver.resolve("target-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.resolved = False

    def test_immutable_unresolved_result(self):
        registry = _build_registry(("target-1", "profile-a"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolver(
            registry
        )

        result = resolver.resolve("target-does-not-exist")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.resolved = True

    def test_does_not_mutate_registry(self):
        registry = _build_registry(("target-1", "profile-a"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolver(
            registry
        )

        resolver.resolve("target-does-not-exist")

        assert registry.contains("target-1") is True
        assert len(registry.list()) == 1


class TestRejectNoneRegistry:
    """Constructing a resolver against a None registry is rejected."""

    def test_reject_none_registry(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolverError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolver(
                None
            )


class TestRejectNoneTargetId:
    """Resolving a None target ID is rejected."""

    def test_reject_none_target_id(self):
        registry = _build_registry(("target-1", "profile-a"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolver(
            registry
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolverError
        ):
            resolver.resolve(None)


class TestRejectBlankTargetId:
    """Resolving a blank target ID is rejected."""

    def test_reject_blank_target_id(self):
        registry = _build_registry(("target-1", "profile-a"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolver(
            registry
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolverError
        ):
            resolver.resolve("   ")


class TestRejectInvalidResolutionSource:
    """A resolved result carrying an invalid resolution source is rejected."""

    def test_reject_invalid_resolution_source(self):
        assignment = _build_assignment("target-1", "profile-a")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResult(
                target_id="target-1",

                assignment=assignment,

                resolved=True,

                resolution_source="not-a-real-source",
            )

    def test_reject_resolved_without_assignment(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResult(
                target_id="target-1",

                assignment=None,

                resolved=True,

                resolution_source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionSource.REGISTRY,
            )

    def test_reject_unresolved_with_assignment(self):
        assignment = _build_assignment("target-1", "profile-a")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResult(
                target_id="target-1",

                assignment=assignment,

                resolved=False,

                resolution_source=None,
            )

    def test_reject_unresolved_with_source(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResult(
                target_id="target-1",

                assignment=None,

                resolved=False,

                resolution_source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionSource.REGISTRY,
            )
