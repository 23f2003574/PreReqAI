import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityRule,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilitySeverity,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolver,
)


class FakeClock:
    def __init__(self, now):
        self.current = now

    def now(self):
        return self.current


def _binding(binding_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id="development",
        capability_id="capability-a",
        created_at=datetime.now(timezone.utc),
    )


def _template(template_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
        template_id=template_id,
        name=template_id,
        binding_ids=binding_ids,
        metadata={},
    )


def _preset(preset_id, binding_template_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset(
        preset_id=preset_id,
        name=preset_id,
        description="A preset.",
        binding_template_ids=binding_template_ids,
    )


def _group(group_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
        group_id=group_id,
        group_name=group_id,
        binding_ids=binding_ids,
    )


def _workspace(
    workspace_id,
    binding_ids=(),
    template_ids=(),
    preset_ids=(),
    group_ids=(),
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace(
        workspace_id=workspace_id,
        name=workspace_id,
        description="A workspace.",
        binding_ids=binding_ids,
        template_ids=template_ids,
        preset_ids=preset_ids,
        group_ids=group_ids,
    )


def _build_context(
    binding_ids=("binding-1", "binding-2"),
    template_specs=(("template-1", ()),),
    preset_specs=(("preset-1", ()),),
    group_specs=(("group-1", ()),),
):
    clock = FakeClock(datetime.now(timezone.utc))

    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()
    for binding_id in binding_ids:
        binding_registry.register(_binding(binding_id))
    binding_activation = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(binding_registry, clock)
    for binding_id in binding_ids:
        binding_activation.activate(binding_id)

    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()
    for template_id, template_binding_ids in template_specs:
        template_registry.register(_template(template_id, binding_ids=template_binding_ids))
    template_activation = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(template_registry, clock)
    for template_id, _ in template_specs:
        template_activation.activate(template_id)

    preset_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()
    for preset_id, preset_template_ids in preset_specs:
        preset_registry.register(_preset(preset_id, binding_template_ids=preset_template_ids))
    preset_activation = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(preset_registry, clock)
    for preset_id, _ in preset_specs:
        preset_activation.activate(preset_id)

    group_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()
    for group_id, group_binding_ids in group_specs:
        group_registry.register(_group(group_id, binding_ids=group_binding_ids))
    group_activation = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(group_registry, clock)
    for group_id, _ in group_specs:
        group_activation.activate(group_id)

    workspace_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()

    resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolver(
        workspace_registry,
        binding_registry,
        binding_activation,
        template_registry,
        template_activation,
        preset_registry,
        preset_activation,
        group_registry,
        group_activation,
    )

    return {
        "workspace_registry": workspace_registry,
        "resolver": resolver,
        "binding_registry": binding_registry,
        "template_registry": template_registry,
        "preset_registry": preset_registry,
        "group_registry": group_registry,
    }


def _build_service(context, rules=None):
    kwargs = {"rules": rules} if rules is not None else {}

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityService(
        context["resolver"],
        context["binding_registry"],
        context["template_registry"],
        context["preset_registry"],
        context["group_registry"],
        **kwargs,
    )


class TestCompatibleWorkspace:
    def test_compatible_workspace(self):
        context = _build_context()
        context["workspace_registry"].register(
            _workspace("workspace-1", binding_ids=("binding-1",), template_ids=("template-1",))
        )
        service = _build_service(context)

        result = service.check("workspace-1")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityResult)
        assert result.compatible is True
        assert result.violations == ()


class TestIncompatibleWorkspace:
    def test_empty_resources(self):
        context = _build_context()
        context["workspace_registry"].register(_workspace("workspace-1"))
        service = _build_service(context)

        result = service.check("workspace-1")

        assert result.compatible is False
        assert any(v.rule_id == "non_empty_resources" for v in result.violations)

    def test_overlapping_bindings(self):
        context = _build_context(template_specs=(("template-1", ("binding-1",)),))
        context["workspace_registry"].register(
            _workspace("workspace-1", binding_ids=("binding-1",), template_ids=("template-1",))
        )
        service = _build_service(context)

        result = service.check("workspace-1")

        assert result.compatible is False
        assert any(v.rule_id == "no_overlapping_bindings" for v in result.violations)

    def test_overlapping_templates(self):
        context = _build_context(preset_specs=(("preset-1", ("template-1",)),))
        context["workspace_registry"].register(
            _workspace("workspace-1", template_ids=("template-1",), preset_ids=("preset-1",))
        )
        service = _build_service(context)

        result = service.check("workspace-1")

        assert any(v.rule_id == "no_overlapping_templates" for v in result.violations)


class TestSupports:
    def test_supports_true(self):
        context = _build_context()
        context["workspace_registry"].register(_workspace("workspace-1", binding_ids=("binding-1",)))
        service = _build_service(context)

        assert service.supports("workspace-1") is True

    def test_supports_false(self):
        context = _build_context()
        context["workspace_registry"].register(_workspace("workspace-1"))
        service = _build_service(context)

        assert service.supports("workspace-1") is False


class TestMultipleViolationsCollected:
    def test_multiple_violations_collected(self):
        context = _build_context(template_specs=(("template-1", ("binding-1",)),), preset_specs=(("preset-1", ("template-1",)),))
        context["workspace_registry"].register(
            _workspace(
                "workspace-1",
                binding_ids=("binding-1",),
                template_ids=("template-1",),
                preset_ids=("preset-1",),
            )
        )
        service = _build_service(context)

        result = service.check("workspace-1")

        assert result.compatible is False

        rule_ids = {v.rule_id for v in result.violations}

        assert "no_overlapping_bindings" in rule_ids
        assert "no_overlapping_templates" in rule_ids
        assert len(result.violations) >= 2


class TestDeterministicEvaluation:
    def test_deterministic_evaluation(self):
        context = _build_context()
        context["workspace_registry"].register(_workspace("workspace-1", binding_ids=("binding-1",)))
        service = _build_service(context)

        first = service.check("workspace-1")
        second = service.check("workspace-1")

        assert first.compatible == second.compatible
        assert first.violations == second.violations

    def test_rules_evaluated_in_declared_order(self):
        context = _build_context()
        service = _build_service(context)

        assert [rule.rule_id for rule in service.rules()] == [
            "non_empty_resources",
            "no_overlapping_bindings",
            "no_overlapping_templates",
        ]


class TestImmutableResult:
    def test_immutable_result(self):
        context = _build_context()
        context["workspace_registry"].register(_workspace("workspace-1", binding_ids=("binding-1",)))
        service = _build_service(context)

        result = service.check("workspace-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.compatible = False

    def test_immutable_violations(self):
        context = _build_context()
        context["workspace_registry"].register(_workspace("workspace-1"))
        service = _build_service(context)

        result = service.check("workspace-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.violations[0].rule_id = "changed"


class TestValidate:
    def test_validate_raises_on_incompatible_workspace(self):
        context = _build_context()
        service = _build_service(context)

        workspace = _workspace("workspace-1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError):
            service.validate(workspace)

    def test_validate_passes_on_compatible_workspace(self):
        context = _build_context()
        service = _build_service(context)

        workspace = _workspace("workspace-1", binding_ids=("binding-1",))

        service.validate(workspace)

    def test_validate_none_workspace(self):
        context = _build_context()
        service = _build_service(context)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError):
            service.validate(None)


class TestRejectInvalidIdentifiers:
    def test_reject_blank_workspace_id(self):
        context = _build_context()
        service = _build_service(context)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError):
            service.check("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError):
            service.check(None)

    def test_reject_unknown_workspace(self):
        context = _build_context()
        service = _build_service(context)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError):
            service.check("workspace-missing")


class TestRejectDuplicateRuleIds:
    def test_reject_duplicate_rule_ids(self):
        context = _build_context()

        duplicate_rules = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityRule(
                rule_id="non_empty_resources",
                severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilitySeverity.ERROR,
            ),
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityRule(
                rule_id="non_empty_resources",
                severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilitySeverity.WARNING,
            ),
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError):
            _build_service(context, rules=duplicate_rules)
