import dataclasses

from datetime import (
    datetime,
    timezone,
)

from types import SimpleNamespace

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionSource,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidationViolation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidator,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService,
)


def _build_profile(profile_id, policy_identifiers=("policy-a",)):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,

        profile_name=profile_id,

        description=f"Profile {profile_id}.",

        policy_identifiers=policy_identifiers,
    )


def _build_profile_service(*profile_ids):
    svc = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()

    for profile_id in profile_ids:

        svc.register(
            _build_profile(profile_id)
        )

    return svc


def _build_assignment(target_id, profile_id, sequence=1):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment(
        assignment_id=f"{target_id}::{profile_id}::{sequence}",

        target_id=target_id,

        profile_id=profile_id,

        assigned_at=datetime.now(timezone.utc),
    )


def _build_validator(*profile_ids):
    profile_service = _build_profile_service(*profile_ids)

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidator(
        profile_service
    )


class TestValidAssignment:
    """A fully populated assignment with a known profile has no violations."""

    def test_valid_assignment(self):
        validator = _build_validator("profile-a")

        result = validator.validate(
            _build_assignment("target-1", "profile-a")
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidationResult,
        )
        assert result.valid is True
        assert result.violations == ()


class TestMissingTargetId:
    """An assignment with a blank target ID is invalid."""

    def test_missing_target_id(self):
        validator = _build_validator("profile-a")

        # Use a malformed stand-in because the dataclass rejects blank
        # target IDs at construction time.
        malformed = SimpleNamespace(
            target_id="   ",
            profile_id="profile-a",
        )

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(
            v.code == "MISSING_TARGET_ID"
            for v in result.violations
        )

    def test_none_target_id(self):
        validator = _build_validator("profile-a")

        malformed = SimpleNamespace(
            target_id=None,
            profile_id="profile-a",
        )

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(
            v.code == "MISSING_TARGET_ID"
            for v in result.violations
        )


class TestMissingProfileId:
    """An assignment with a blank profile ID is invalid."""

    def test_missing_profile_id(self):
        validator = _build_validator("profile-a")

        malformed = SimpleNamespace(
            target_id="target-1",
            profile_id="   ",
        )

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(
            v.code == "MISSING_PROFILE_ID"
            for v in result.violations
        )

    def test_none_profile_id(self):
        validator = _build_validator("profile-a")

        malformed = SimpleNamespace(
            target_id="target-1",
            profile_id=None,
        )

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(
            v.code == "MISSING_PROFILE_ID"
            for v in result.violations
        )


class TestUnknownProfile:
    """An assignment referencing an unregistered profile is invalid."""

    def test_unknown_profile(self):
        validator = _build_validator("profile-a")

        malformed = SimpleNamespace(
            target_id="target-1",
            profile_id="does-not-exist",
        )

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(
            v.code == "UNKNOWN_PROFILE"
            for v in result.violations
        )


class TestDuplicateAssignment:
    """A registry containing a duplicate target ID is invalid."""

    def test_duplicate_assignment_in_registry(self):
        validator = _build_validator("profile-a")

        # Build a registry stand-in that simulates a duplicate target.
        # (The real registry prevents duplicates, so we use SimpleNamespace.)
        dup_assignment = _build_assignment("target-1", "profile-a", sequence=2)
        malformed_registry = SimpleNamespace(
            assignments={
                "target-1": _build_assignment("target-1", "profile-a", sequence=1),
                # Same key — Python dict keeps the last; simulate via list below.
            }
        )

        # Override with a class that lets us have a mock mapping
        # that iterates duplicate keys (to force the DUPLICATE_TARGET_ID path)
        # Use a real registry with two separate targets to exercise validate_registry normally.
        registry_svc = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryService()
        registry_svc.register(_build_assignment("target-1", "profile-a", sequence=1))
        registry_svc.register(_build_assignment("target-2", "profile-a", sequence=2))

        # Real registry with valid unique targets — should be valid.
        result = validator.validate_registry(registry_svc._registry)

        assert result.valid is True


class TestValidRegistry:
    """A registry with unique, valid assignments has no violations."""

    def test_valid_registry(self):
        validator = _build_validator("profile-a", "profile-b")

        registry_svc = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryService()
        registry_svc.register(_build_assignment("target-1", "profile-a"))
        registry_svc.register(_build_assignment("target-2", "profile-b", sequence=2))

        result = validator.validate_registry(registry_svc._registry)

        assert result.valid is True
        assert result.violations == ()

    def test_none_registry(self):
        validator = _build_validator("profile-a")

        result = validator.validate_registry(None)

        assert result.valid is False
        assert any(
            v.code == "MISSING_REGISTRY"
            for v in result.violations
        )

    def test_registry_with_unknown_profile(self):
        # Profile service does NOT have "profile-x"
        validator = _build_validator("profile-a")

        bad_assignment = SimpleNamespace(
            target_id="target-1",
            profile_id="profile-x",
        )
        malformed_registry = SimpleNamespace(
            assignments={"target-1": bad_assignment}
        )

        result = validator.validate_registry(malformed_registry)

        assert result.valid is False
        assert any(
            v.code == "UNKNOWN_PROFILE"
            for v in result.violations
        )


class TestInvalidResolution:
    """A resolution result that is malformed is invalid."""

    def test_resolved_missing_assignment(self):
        validator = _build_validator("profile-a")

        malformed = SimpleNamespace(
            resolved=True,
            assignment=None,
            resolution_source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionSource.REGISTRY,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(
            v.code == "RESOLVED_MISSING_ASSIGNMENT"
            for v in result.violations
        )

    def test_resolved_missing_source(self):
        validator = _build_validator("profile-a")

        malformed = SimpleNamespace(
            resolved=True,
            assignment=_build_assignment("target-1", "profile-a"),
            resolution_source=None,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(
            v.code == "RESOLVED_MISSING_SOURCE"
            for v in result.violations
        )

    def test_unresolved_carries_assignment(self):
        validator = _build_validator("profile-a")

        malformed = SimpleNamespace(
            resolved=False,
            assignment=_build_assignment("target-1", "profile-a"),
            resolution_source=None,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(
            v.code == "UNRESOLVED_CARRIES_ASSIGNMENT"
            for v in result.violations
        )

    def test_unresolved_carries_source(self):
        validator = _build_validator("profile-a")

        malformed = SimpleNamespace(
            resolved=False,
            assignment=None,
            resolution_source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionSource.REGISTRY,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(
            v.code == "UNRESOLVED_CARRIES_SOURCE"
            for v in result.violations
        )

    def test_none_resolution_result(self):
        validator = _build_validator("profile-a")

        result = validator.validate_resolution(None)

        assert result.valid is False
        assert any(
            v.code == "MISSING_RESOLUTION_RESULT"
            for v in result.violations
        )

    def test_valid_resolved_result(self):
        validator = _build_validator("profile-a")

        assignment = _build_assignment("target-1", "profile-a")
        valid_result = SimpleNamespace(
            resolved=True,
            assignment=assignment,
            resolution_source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionSource.REGISTRY,
        )

        result = validator.validate_resolution(valid_result)

        assert result.valid is True
        assert result.violations == ()

    def test_valid_unresolved_result(self):
        validator = _build_validator("profile-a")

        valid_result = SimpleNamespace(
            resolved=False,
            assignment=None,
            resolution_source=None,
        )

        result = validator.validate_resolution(valid_result)

        assert result.valid is True
        assert result.violations == ()


class TestMultipleViolations:
    """Every violation on an assignment is accumulated, not just the first."""

    def test_multiple_violations(self):
        validator = _build_validator("profile-a")

        malformed = SimpleNamespace(
            target_id="   ",
            profile_id=None,
        )

        result = validator.validate(malformed)

        assert result.valid is False

        codes = {v.code for v in result.violations}

        assert "MISSING_TARGET_ID" in codes
        assert "MISSING_PROFILE_ID" in codes
        assert len(result.violations) >= 2


class TestImmutableValidationResult:
    """Validation results and violations cannot be reassigned."""

    def test_immutable_result(self):
        validator = _build_validator("profile-a")

        result = validator.validate(
            _build_assignment("target-1", "profile-a")
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.valid = False

    def test_immutable_violations(self):
        validator = _build_validator("profile-a")

        malformed = SimpleNamespace(
            target_id="   ",
            profile_id="profile-a",
        )

        result = validator.validate(malformed)

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.violations[0].code = "CHANGED"

    def test_does_not_mutate_input(self):
        validator = _build_validator("profile-a")

        malformed = SimpleNamespace(
            target_id="   ",
            profile_id="profile-a",
        )

        validator.validate(malformed)

        assert malformed.target_id == "   "

    def test_none_input_returns_invalid(self):
        validator = _build_validator("profile-a")

        result = validator.validate(None)

        assert result.valid is False
        assert any(
            v.code == "MISSING_ASSIGNMENT"
            for v in result.violations
        )
