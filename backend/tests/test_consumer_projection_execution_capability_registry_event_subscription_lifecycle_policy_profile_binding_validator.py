import dataclasses

from datetime import (
    datetime,
    timezone,
)

from types import SimpleNamespace

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionSource,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidator,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService,
)


class _CapabilityRegistry:
    def __init__(self, *capability_ids):
        self._capability_ids = set(capability_ids)

    def contains(self, capability_id):
        return capability_id in self._capability_ids


def _build_profile(profile_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,
        profile_name=profile_id,
        description=f"Profile {profile_id}.",
        policy_identifiers=(f"policy-{profile_id}",),
    )


def _build_profile_service(*profile_ids):
    service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()

    for profile_id in profile_ids:
        service.register(_build_profile(profile_id))

    return service


def _build_binding(binding_id, profile_id, capability_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id=profile_id,
        capability_id=capability_id,
        created_at=datetime.now(timezone.utc),
    )


def _build_validator(profile_ids=("profile-a",), capability_ids=("capability-a",)):
    profile_service = _build_profile_service(*profile_ids)
    capability_registry = _CapabilityRegistry(*capability_ids)

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidator(
        profile_service,
        capability_registry,
    )


class TestValidBinding:
    def test_valid_binding(self):
        validator = _build_validator()

        result = validator.validate(_build_binding("binding-1", "profile-a", "capability-a"))

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidationResult)
        assert result.valid is True
        assert result.violations == ()

    def test_none_binding(self):
        validator = _build_validator()

        result = validator.validate(None)

        assert result.valid is False
        assert any(v.code == "MISSING_BINDING" for v in result.violations)


class TestMissingProfile:
    def test_missing_profile_id(self):
        validator = _build_validator()

        malformed = SimpleNamespace(binding_id="binding-1", profile_id="   ", capability_id="capability-a")

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "MISSING_PROFILE_ID" for v in result.violations)

    def test_unknown_profile(self):
        validator = _build_validator()

        malformed = SimpleNamespace(binding_id="binding-1", profile_id="does-not-exist", capability_id="capability-a")

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "UNKNOWN_PROFILE" for v in result.violations)


class TestMissingCapability:
    def test_missing_capability_id(self):
        validator = _build_validator()

        malformed = SimpleNamespace(binding_id="binding-1", profile_id="profile-a", capability_id=None)

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "MISSING_CAPABILITY_ID" for v in result.violations)

    def test_unknown_capability(self):
        validator = _build_validator()

        malformed = SimpleNamespace(binding_id="binding-1", profile_id="profile-a", capability_id="does-not-exist")

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "UNKNOWN_CAPABILITY" for v in result.violations)


class TestDuplicateBindingPair:
    def test_duplicate_binding_pair_in_registry(self):
        validator = _build_validator()

        malformed_registry = SimpleNamespace(
            bindings={
                "binding-1": _build_binding("binding-1", "profile-a", "capability-a"),
                "binding-2": _build_binding("binding-2", "profile-a", "capability-a"),
            }
        )

        result = validator.validate_registry(malformed_registry)

        assert result.valid is False
        assert any(v.code == "DUPLICATE_BINDING_PAIR" for v in result.violations)


class TestRegistryValidation:
    def test_valid_registry(self):
        validator = _build_validator(capability_ids=("capability-a", "capability-b"))

        registry_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()
        registry_service.register(_build_binding("binding-1", "profile-a", "capability-a"))
        registry_service.register(_build_binding("binding-2", "profile-a", "capability-b"))

        result = validator.validate_registry(registry_service._registry)

        assert result.valid is True
        assert result.violations == ()

    def test_none_registry(self):
        validator = _build_validator()

        result = validator.validate_registry(None)

        assert result.valid is False
        assert any(v.code == "MISSING_REGISTRY" for v in result.violations)

    def test_registry_with_unknown_profile(self):
        validator = _build_validator()

        malformed_registry = SimpleNamespace(
            bindings={"binding-1": SimpleNamespace(binding_id="binding-1", profile_id="profile-x", capability_id="capability-a")}
        )

        result = validator.validate_registry(malformed_registry)

        assert result.valid is False
        assert any(v.code == "UNKNOWN_PROFILE" for v in result.violations)


class TestResolutionValidation:
    def test_resolved_missing_binding(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            resolved=True,
            binding=None,
            source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionSource.REGISTRY,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(v.code == "RESOLVED_MISSING_BINDING" for v in result.violations)

    def test_resolved_missing_source(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            resolved=True,
            binding=_build_binding("binding-1", "profile-a", "capability-a"),
            source=None,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(v.code == "RESOLVED_MISSING_SOURCE" for v in result.violations)

    def test_unresolved_carries_binding(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            resolved=False,
            binding=_build_binding("binding-1", "profile-a", "capability-a"),
            source=None,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(v.code == "UNRESOLVED_CARRIES_BINDING" for v in result.violations)

    def test_none_resolution_result(self):
        validator = _build_validator()

        result = validator.validate_resolution(None)

        assert result.valid is False
        assert any(v.code == "MISSING_RESOLUTION_RESULT" for v in result.violations)

    def test_valid_resolved_result(self):
        validator = _build_validator()

        valid_result = SimpleNamespace(
            resolved=True,
            binding=_build_binding("binding-1", "profile-a", "capability-a"),
            source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionSource.REGISTRY,
        )

        result = validator.validate_resolution(valid_result)

        assert result.valid is True
        assert result.violations == ()

    def test_valid_unresolved_result(self):
        validator = _build_validator()

        valid_result = SimpleNamespace(resolved=False, binding=None, source=None)

        result = validator.validate_resolution(valid_result)

        assert result.valid is True
        assert result.violations == ()


class TestMultipleViolations:
    def test_multiple_violations(self):
        validator = _build_validator()

        malformed = SimpleNamespace(binding_id="binding-1", profile_id=None, capability_id=None)

        result = validator.validate(malformed)

        assert result.valid is False

        codes = {v.code for v in result.violations}

        assert "MISSING_PROFILE_ID" in codes
        assert "MISSING_CAPABILITY_ID" in codes
        assert len(result.violations) >= 2


class TestImmutableValidationResult:
    def test_immutable_result(self):
        validator = _build_validator()

        result = validator.validate(_build_binding("binding-1", "profile-a", "capability-a"))

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.valid = False

    def test_immutable_violations(self):
        validator = _build_validator()

        malformed = SimpleNamespace(binding_id="binding-1", profile_id="   ", capability_id="capability-a")

        result = validator.validate(malformed)

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.violations[0].code = "CHANGED"

    def test_does_not_mutate_input(self):
        validator = _build_validator()

        malformed = SimpleNamespace(binding_id="binding-1", profile_id="   ", capability_id="capability-a")

        validator.validate(malformed)

        assert malformed.profile_id == "   "
