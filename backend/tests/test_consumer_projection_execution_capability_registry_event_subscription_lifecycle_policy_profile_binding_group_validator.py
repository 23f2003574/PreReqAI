import dataclasses

from types import SimpleNamespace

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionSource,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidator,
)


class _BindingRegistry:
    def __init__(self, *binding_ids):
        self._binding_ids = set(binding_ids)

    def contains(self, binding_id):
        return binding_id in self._binding_ids


def _build_group(group_id, group_name=None, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
        group_id=group_id,
        group_name=group_name or group_id,
        binding_ids=binding_ids,
    )


def _build_validator(binding_ids=("binding-a", "binding-b")):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidator(
        _BindingRegistry(*binding_ids)
    )


class TestValidGroup:
    def test_valid_group(self):
        validator = _build_validator()

        result = validator.validate(_build_group("group-1", binding_ids=("binding-a", "binding-b")))

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidationResult)
        assert result.valid is True
        assert result.violations == ()

    def test_none_group(self):
        validator = _build_validator()

        result = validator.validate(None)

        assert result.valid is False
        assert any(v.code == "MISSING_GROUP" for v in result.violations)


class TestMissingGroupIdentity:
    def test_missing_group_id(self):
        validator = _build_validator()

        malformed = SimpleNamespace(group_id="   ", group_name="Group", binding_ids=("binding-a",))

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "MISSING_GROUP_ID" for v in result.violations)

    def test_missing_group_name(self):
        validator = _build_validator()

        malformed = SimpleNamespace(group_id="group-1", group_name=None, binding_ids=("binding-a",))

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "MISSING_GROUP_NAME" for v in result.violations)


class TestUnknownBinding:
    def test_unknown_binding(self):
        validator = _build_validator()

        malformed = SimpleNamespace(group_id="group-1", group_name="Group", binding_ids=("binding-does-not-exist",))

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "UNKNOWN_BINDING" for v in result.violations)


class TestDuplicateMembers:
    def test_duplicate_members(self):
        validator = _build_validator()

        malformed = SimpleNamespace(group_id="group-1", group_name="Group", binding_ids=("binding-a", "binding-a"))

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "DUPLICATE_MEMBER" for v in result.violations)


class TestRegistryValidation:
    def test_valid_registry(self):
        validator = _build_validator()

        registry_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()
        registry_service.register(_build_group("group-1", binding_ids=("binding-a",)))
        registry_service.register(_build_group("group-2", binding_ids=("binding-b",)))

        result = validator.validate_registry(registry_service._registry)

        assert result.valid is True
        assert result.violations == ()

    def test_none_registry(self):
        validator = _build_validator()

        result = validator.validate_registry(None)

        assert result.valid is False
        assert any(v.code == "MISSING_REGISTRY" for v in result.violations)

    def test_registry_with_unknown_binding(self):
        validator = _build_validator()

        malformed_registry = SimpleNamespace(
            groups={
                "group-1": SimpleNamespace(
                    group_id="group-1",
                    group_name="Group",
                    binding_ids=("binding-does-not-exist",),
                )
            }
        )

        result = validator.validate_registry(malformed_registry)

        assert result.valid is False
        assert any(v.code == "UNKNOWN_BINDING" for v in result.violations)


class TestResolutionValidation:
    def test_resolved_missing_group(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            resolved=True,
            group=None,
            bindings=(),
            source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionSource.REGISTRY,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(v.code == "RESOLVED_MISSING_GROUP" for v in result.violations)

    def test_resolved_missing_source(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            resolved=True,
            group=_build_group("group-1", binding_ids=("binding-a",)),
            bindings=(),
            source=None,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(v.code == "RESOLVED_MISSING_SOURCE" for v in result.violations)

    def test_unresolved_carries_group(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            resolved=False,
            group=_build_group("group-1", binding_ids=("binding-a",)),
            bindings=(),
            source=None,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(v.code == "UNRESOLVED_CARRIES_GROUP" for v in result.violations)

    def test_none_resolution_result(self):
        validator = _build_validator()

        result = validator.validate_resolution(None)

        assert result.valid is False
        assert any(v.code == "MISSING_RESOLUTION_RESULT" for v in result.violations)

    def test_valid_resolved_result(self):
        validator = _build_validator()

        valid_result = SimpleNamespace(
            resolved=True,
            group=_build_group("group-1", binding_ids=("binding-a",)),
            bindings=(),
            source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionSource.REGISTRY,
        )

        result = validator.validate_resolution(valid_result)

        assert result.valid is True
        assert result.violations == ()

    def test_valid_unresolved_result(self):
        validator = _build_validator()

        valid_result = SimpleNamespace(resolved=False, group=None, bindings=(), source=None)

        result = validator.validate_resolution(valid_result)

        assert result.valid is True
        assert result.violations == ()


class TestMultipleViolations:
    def test_multiple_violations(self):
        validator = _build_validator()

        malformed = SimpleNamespace(group_id=None, group_name=None, binding_ids=("binding-does-not-exist",))

        result = validator.validate(malformed)

        assert result.valid is False

        codes = {v.code for v in result.violations}

        assert "MISSING_GROUP_ID" in codes
        assert "MISSING_GROUP_NAME" in codes
        assert "UNKNOWN_BINDING" in codes
        assert len(result.violations) >= 3


class TestImmutableValidationResult:
    def test_immutable_result(self):
        validator = _build_validator()

        result = validator.validate(_build_group("group-1", binding_ids=("binding-a",)))

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.valid = False

    def test_immutable_violations(self):
        validator = _build_validator()

        malformed = SimpleNamespace(group_id="   ", group_name="Group", binding_ids=("binding-a",))

        result = validator.validate(malformed)

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.violations[0].code = "CHANGED"

    def test_does_not_mutate_input(self):
        validator = _build_validator()

        malformed = SimpleNamespace(group_id="   ", group_name="Group", binding_ids=("binding-a",))

        validator.validate(malformed)

        assert malformed.group_id == "   "
