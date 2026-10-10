import dataclasses

from types import SimpleNamespace

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionSource,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateValidationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateValidator,
)


class _BindingRegistry:
    def __init__(self, *binding_ids):
        self._binding_ids = set(binding_ids)

    def contains(self, binding_id):
        return binding_id in self._binding_ids


def _build_template(template_id, name=None, binding_ids=(), metadata=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
        template_id=template_id,
        name=name or template_id,
        binding_ids=binding_ids,
        metadata=metadata or {},
    )


def _build_validator(binding_ids=("binding-a", "binding-b")):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateValidator(
        _BindingRegistry(*binding_ids)
    )


class TestValidTemplate:
    def test_valid_template(self):
        validator = _build_validator()

        result = validator.validate(_build_template("template-1", binding_ids=("binding-a", "binding-b")))

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateValidationResult)
        assert result.valid is True
        assert result.violations == ()

    def test_none_template(self):
        validator = _build_validator()

        result = validator.validate(None)

        assert result.valid is False
        assert any(v.code == "MISSING_TEMPLATE" for v in result.violations)


class TestMissingTemplateIdentity:
    def test_missing_template_id(self):
        validator = _build_validator()

        malformed = SimpleNamespace(template_id="   ", name="Template", binding_ids=("binding-a",))

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "MISSING_TEMPLATE_ID" for v in result.violations)

    def test_missing_template_name(self):
        validator = _build_validator()

        malformed = SimpleNamespace(template_id="template-1", name=None, binding_ids=("binding-a",))

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "MISSING_TEMPLATE_NAME" for v in result.violations)


class TestUnknownBinding:
    def test_unknown_binding(self):
        validator = _build_validator()

        malformed = SimpleNamespace(template_id="template-1", name="Template", binding_ids=("binding-does-not-exist",))

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "UNKNOWN_BINDING" for v in result.violations)


class TestDuplicateBindingReferences:
    def test_duplicate_bindings(self):
        validator = _build_validator()

        malformed = SimpleNamespace(template_id="template-1", name="Template", binding_ids=("binding-a", "binding-a"))

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "DUPLICATE_MEMBER" for v in result.violations)


class TestRegistryValidation:
    def test_valid_registry(self):
        validator = _build_validator()

        registry_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()
        registry_service.register(_build_template("template-1", binding_ids=("binding-a",)))
        registry_service.register(_build_template("template-2", binding_ids=("binding-b",)))

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
            templates={
                "template-1": SimpleNamespace(
                    template_id="template-1",
                    name="Template",
                    binding_ids=("binding-does-not-exist",),
                )
            }
        )

        result = validator.validate_registry(malformed_registry)

        assert result.valid is False
        assert any(v.code == "UNKNOWN_BINDING" for v in result.violations)


class TestResolutionValidation:
    def test_resolved_missing_template(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            resolved=True,
            template=None,
            bindings=(),
            source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionSource.REGISTRY,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(v.code == "RESOLVED_MISSING_TEMPLATE" for v in result.violations)

    def test_resolved_missing_source(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            resolved=True,
            template=_build_template("template-1", binding_ids=("binding-a",)),
            bindings=(),
            source=None,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(v.code == "RESOLVED_MISSING_SOURCE" for v in result.violations)

    def test_unresolved_carries_template(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            resolved=False,
            template=_build_template("template-1", binding_ids=("binding-a",)),
            bindings=(),
            source=None,
        )

        result = validator.validate_resolution(malformed)

        assert result.valid is False
        assert any(v.code == "UNRESOLVED_CARRIES_TEMPLATE" for v in result.violations)

    def test_none_resolution_result(self):
        validator = _build_validator()

        result = validator.validate_resolution(None)

        assert result.valid is False
        assert any(v.code == "MISSING_RESOLUTION_RESULT" for v in result.violations)

    def test_valid_resolved_result(self):
        validator = _build_validator()

        valid_result = SimpleNamespace(
            resolved=True,
            template=_build_template("template-1", binding_ids=("binding-a",)),
            bindings=(),
            source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionSource.REGISTRY,
        )

        result = validator.validate_resolution(valid_result)

        assert result.valid is True
        assert result.violations == ()

    def test_valid_unresolved_result(self):
        validator = _build_validator()

        valid_result = SimpleNamespace(resolved=False, template=None, bindings=(), source=None)

        result = validator.validate_resolution(valid_result)

        assert result.valid is True
        assert result.violations == ()


class TestMultipleViolations:
    def test_multiple_violations(self):
        validator = _build_validator()

        malformed = SimpleNamespace(template_id=None, name=None, binding_ids=("binding-does-not-exist",))

        result = validator.validate(malformed)

        assert result.valid is False

        codes = {v.code for v in result.violations}

        assert "MISSING_TEMPLATE_ID" in codes
        assert "MISSING_TEMPLATE_NAME" in codes
        assert "UNKNOWN_BINDING" in codes
        assert len(result.violations) >= 3


class TestImmutableValidationResult:
    def test_immutable_result(self):
        validator = _build_validator()

        result = validator.validate(_build_template("template-1", binding_ids=("binding-a",)))

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.valid = False

    def test_immutable_violations(self):
        validator = _build_validator()

        malformed = SimpleNamespace(template_id="   ", name="Template", binding_ids=("binding-a",))

        result = validator.validate(malformed)

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.violations[0].code = "CHANGED"

    def test_does_not_mutate_input(self):
        validator = _build_validator()

        malformed = SimpleNamespace(template_id="   ", name="Template", binding_ids=("binding-a",))

        validator.validate(malformed)

        assert malformed.template_id == "   "
