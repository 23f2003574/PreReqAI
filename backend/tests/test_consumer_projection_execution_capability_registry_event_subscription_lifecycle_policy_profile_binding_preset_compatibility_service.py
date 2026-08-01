import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityRule,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilitySeverity,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameter,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
)


class FakeClock:
    def __init__(self, now):
        self.current = now

    def now(self):
        return self.current


class _StubParameterization:
    def __init__(self, parameters):
        self._parameters = parameters

    def supported_parameters(self, preset_id):
        return self._parameters


def _template(template_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
        template_id=template_id,
        name=template_id,
        binding_ids=("binding-1",),
        metadata={},
    )


def _preset(preset_id, binding_template_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset(
        preset_id=preset_id,
        name=preset_id,
        description="A preset.",
        binding_template_ids=binding_template_ids,
    )


def _parameter(name, type_=str, required=False, default_value=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameter(
        name=name,
        type=type_,
        required=required,
        default_value=default_value,
    )


def _build_context(
    template_ids=("template-1",),
    active_template_ids=None,
    presets=(("preset-1", ("template-1",)),),
    parameter_definitions=None,
):
    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

    for template_id in template_ids:
        template_registry.register(_template(template_id))

    activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(
        template_registry,
        FakeClock(datetime.now(timezone.utc)),
    )

    for template_id in active_template_ids if active_template_ids is not None else template_ids:
        activation_service.activate(template_id)

    preset_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()

    for preset_id, binding_template_ids in presets:
        preset_registry.register(_preset(preset_id, binding_template_ids=binding_template_ids))

    resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
        preset_registry, template_registry, activation_service
    )

    parameterization_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService(
        preset_registry,
        parameter_definitions or {},
    )

    return resolver, template_registry, preset_registry, parameterization_service


def _build_service(
    template_ids=("template-1",),
    active_template_ids=None,
    presets=(("preset-1", ("template-1",)),),
    parameter_definitions=None,
    parameterization_service=None,
    rules=None,
):
    resolver, template_registry, preset_registry, default_parameterization_service = _build_context(
        template_ids=template_ids,
        active_template_ids=active_template_ids,
        presets=presets,
        parameter_definitions=parameter_definitions,
    )

    kwargs = {"rules": rules} if rules is not None else {}

    service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityService(
        resolver,
        template_registry,
        parameterization_service or default_parameterization_service,
        **kwargs,
    )

    return service, resolver, template_registry, preset_registry


class TestCompatiblePreset:
    def test_compatible_preset(self):
        service, *_ = _build_service()

        result = service.check("preset-1")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityResult)
        assert result.compatible is True
        assert result.violations == ()


class TestIncompatiblePreset:
    def test_duplicate_template_targets(self):
        service, *_ = _build_service(
            template_ids=("template-1",),
            presets=(("preset-1", ("template-1", "template-1")),),
        )

        result = service.check("preset-1")

        assert result.compatible is False
        assert any(v.rule_id == "unique_template_targets" for v in result.violations)

    def test_empty_members(self):
        service, *_ = _build_service(
            template_ids=(),
            presets=(("preset-1", ()),),
        )

        result = service.check("preset-1")

        assert result.compatible is False
        assert any(v.rule_id == "non_empty_members" for v in result.violations)


class TestSupports:
    def test_supports_true(self):
        service, *_ = _build_service()

        assert service.supports("preset-1") is True

    def test_supports_false(self):
        service, *_ = _build_service(
            template_ids=("template-1",),
            presets=(("preset-1", ("template-1", "template-1")),),
        )

        assert service.supports("preset-1") is False


class TestMultipleViolationsCollected:
    def test_multiple_violations_collected(self):
        service, *_ = _build_service(
            template_ids=("template-1",),
            presets=(("preset-1", ("template-1", "template-1")),),
            parameterization_service=_StubParameterization((_parameter("region"), _parameter("region"))),
        )

        result = service.check("preset-1")

        assert result.compatible is False

        rule_ids = {v.rule_id for v in result.violations}

        assert "unique_template_targets" in rule_ids
        assert "unique_parameter_names" in rule_ids
        assert len(result.violations) >= 2


class TestDeterministicEvaluation:
    def test_deterministic_evaluation(self):
        service, *_ = _build_service()

        first = service.check("preset-1")
        second = service.check("preset-1")

        assert first.compatible == second.compatible
        assert first.violations == second.violations

    def test_rules_evaluated_in_declared_order(self):
        service, *_ = _build_service()

        assert [rule.rule_id for rule in service.rules()] == [
            "non_empty_members",
            "unique_template_targets",
            "unique_parameter_names",
        ]


class TestImmutableResult:
    def test_immutable_result(self):
        service, *_ = _build_service()

        result = service.check("preset-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.compatible = False

    def test_immutable_violations(self):
        service, *_ = _build_service(
            template_ids=("template-1",),
            presets=(("preset-1", ("template-1", "template-1")),),
        )

        result = service.check("preset-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.violations[0].rule_id = "changed"


class TestValidate:
    def test_validate_raises_on_incompatible_preset(self):
        service, _, template_registry, _ = _build_service(
            template_ids=("template-1",),
            presets=(),
        )

        preset = _preset("preset-1", binding_template_ids=("template-1", "template-1"))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError):
            service.validate(preset)

    def test_validate_passes_on_compatible_preset(self):
        service, *_ = _build_service(presets=())

        preset = _preset("preset-1", binding_template_ids=("template-1",))

        service.validate(preset)

    def test_validate_none_preset(self):
        service, *_ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError):
            service.validate(None)


class TestRejectInvalidIdentifiers:
    def test_reject_blank_preset_id(self):
        service, *_ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError):
            service.check("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError):
            service.check(None)

    def test_reject_unknown_preset(self):
        service, *_ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError):
            service.check("preset-missing")


class TestRejectDuplicateRuleIds:
    def test_reject_duplicate_rule_ids(self):
        duplicate_rules = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityRule(
                rule_id="non_empty_members",
                severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilitySeverity.ERROR,
            ),
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityRule(
                rule_id="non_empty_members",
                severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilitySeverity.WARNING,
            ),
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError):
            _build_service(rules=duplicate_rules)
