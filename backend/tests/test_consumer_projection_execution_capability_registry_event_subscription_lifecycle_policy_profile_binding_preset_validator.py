import dataclasses

from types import SimpleNamespace

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionSource,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetValidationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetValidator,
)


class _TemplateRegistry:
    def __init__(self, *template_ids):
        self._template_ids = set(template_ids)

    def contains(self, template_id):
        return template_id in self._template_ids


def _build_preset(preset_id, name=None, description="A preset.", binding_template_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset(
        preset_id=preset_id,
        name=name or preset_id,
        description=description,
        binding_template_ids=binding_template_ids,
    )


def _build_validator(template_ids=("template-a", "template-b")):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetValidator(
        _TemplateRegistry(*template_ids)
    )


class TestValidPreset:
    def test_valid_preset(self):
        validator = _build_validator()

        result = validator.validate(_build_preset("preset-1", binding_template_ids=("template-a", "template-b")))

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetValidationResult)
        assert result.valid is True
        assert result.violations == ()

    def test_none_preset(self):
        validator = _build_validator()

        result = validator.validate(None)

        assert result.valid is False
        assert any(v.code == "MISSING_PRESET" for v in result.violations)


class TestMissingPresetIdentity:
    def test_missing_preset_id(self):
        validator = _build_validator()

        malformed = SimpleNamespace(preset_id="   ", name="Preset", binding_template_ids=("template-a",))

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "MISSING_PRESET_ID" for v in result.violations)

    def test_missing_preset_name(self):
        validator = _build_validator()

        malformed = SimpleNamespace(preset_id="preset-1", name=None, binding_template_ids=("template-a",))

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "MISSING_PRESET_NAME" for v in result.violations)


class TestUnknownTemplate:
    def test_unknown_template(self):
        validator = _build_validator()

        malformed = SimpleNamespace(preset_id="preset-1", name="Preset", binding_template_ids=("template-does-not-exist",))

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "UNKNOWN_TEMPLATE" for v in result.violations)


class TestDuplicateTemplateReferences:
    def test_duplicate_templates(self):
        validator = _build_validator()

        malformed = SimpleNamespace(preset_id="preset-1", name="Preset", binding_template_ids=("template-a", "template-a"))

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "DUPLICATE_MEMBER" for v in result.violations)


class TestRegistryValidation:
    def test_valid_registry(self):
        validator = _build_validator()

        registry_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()
        registry_service.register(_build_preset("preset-1", binding_template_ids=("template-a",)))
        registry_service.register(_build_preset("preset-2", binding_template_ids=("template-b",)))

        result = validator.validate_registry(registry_service._registry)

        assert result.valid is True
        assert result.violations == ()

    def test_none_registry(self):
        validator = _build_validator()

        result = validator.validate_registry(None)

        assert result.valid is False
        assert any(v.code == "MISSING_REGISTRY" for v in result.violations)

    def test_registry_with_unknown_template(self):
        validator = _build_validator()

        malformed_registry = SimpleNamespace(
            presets={
                "preset-1": SimpleNamespace(
                    preset_id="preset-1",
                    name="Preset",
                    binding_template_ids=("template-does-not-exist",),
                )
            }
        )

        result = validator.validate_registry(malformed_registry)

        assert result.valid is False
        assert any(v.code == "UNKNOWN_TEMPLATE" for v in result.violations)


class TestResolutionValidation:
    def test_resolved_missing_preset(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            resolved=True,
            preset=None,
            templates=(),
            source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionSource.REGISTRY,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(v.code == "RESOLVED_MISSING_PRESET" for v in result.violations)

    def test_resolved_missing_source(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            resolved=True,
            preset=_build_preset("preset-1", binding_template_ids=("template-a",)),
            templates=(),
            source=None,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(v.code == "RESOLVED_MISSING_SOURCE" for v in result.violations)

    def test_unresolved_carries_preset(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            resolved=False,
            preset=_build_preset("preset-1", binding_template_ids=("template-a",)),
            templates=(),
            source=None,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(v.code == "UNRESOLVED_CARRIES_PRESET" for v in result.violations)

    def test_none_resolution_result(self):
        validator = _build_validator()

        result = validator.validate_resolution(None)

        assert result.valid is False
        assert any(v.code == "MISSING_RESOLUTION_RESULT" for v in result.violations)

    def test_valid_resolved_result(self):
        validator = _build_validator()

        valid_result = SimpleNamespace(
            resolved=True,
            preset=_build_preset("preset-1", binding_template_ids=("template-a",)),
            templates=(),
            source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionSource.REGISTRY,
        )

        result = validator.validate_resolution(valid_result)

        assert result.valid is True
        assert result.violations == ()

    def test_valid_unresolved_result(self):
        validator = _build_validator()

        valid_result = SimpleNamespace(resolved=False, preset=None, templates=(), source=None)

        result = validator.validate_resolution(valid_result)

        assert result.valid is True
        assert result.violations == ()


class TestMultipleViolations:
    def test_multiple_violations(self):
        validator = _build_validator()

        malformed = SimpleNamespace(preset_id=None, name=None, binding_template_ids=("template-does-not-exist",))

        result = validator.validate(malformed)

        assert result.valid is False

        codes = {v.code for v in result.violations}

        assert "MISSING_PRESET_ID" in codes
        assert "MISSING_PRESET_NAME" in codes
        assert "UNKNOWN_TEMPLATE" in codes
        assert len(result.violations) >= 3


class TestImmutableValidationResult:
    def test_immutable_result(self):
        validator = _build_validator()

        result = validator.validate(_build_preset("preset-1", binding_template_ids=("template-a",)))

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.valid = False

    def test_immutable_violations(self):
        validator = _build_validator()

        malformed = SimpleNamespace(preset_id="   ", name="Preset", binding_template_ids=("template-a",))

        result = validator.validate(malformed)

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.violations[0].code = "CHANGED"

    def test_does_not_mutate_input(self):
        validator = _build_validator()

        malformed = SimpleNamespace(preset_id="   ", name="Preset", binding_template_ids=("template-a",))

        validator.validate(malformed)

        assert malformed.preset_id == "   "
