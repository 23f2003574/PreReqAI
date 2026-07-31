import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityRule,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilitySeverity,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver,
)


class FakeClock:
    def __init__(self, now):
        self.current = now

    def now(self):
        return self.current


def _binding(binding_id, profile_id, capability_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id=profile_id,
        capability_id=capability_id,
        created_at=datetime.now(timezone.utc),
    )


def _template(template_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
        template_id=template_id,
        name=template_id,
        binding_ids=binding_ids,
        metadata={},
    )


def _build_context(bindings=(("binding-1", "profile-a", "capability-a"),), templates=()):
    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

    activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(
        binding_registry,
        FakeClock(datetime.now(timezone.utc)),
    )

    for binding_id, profile_id, capability_id in bindings:
        binding_registry.register(_binding(binding_id, profile_id, capability_id))
        activation_service.activate(binding_id)

    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

    for template_id, binding_ids in templates:
        template_registry.register(_template(template_id, binding_ids=binding_ids))

    resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
        template_registry, binding_registry, activation_service
    )

    return resolver, binding_registry, template_registry


def _build_service(
    bindings=(("binding-1", "profile-a", "capability-a"),),
    templates=(("template-1", ("binding-1",)),),
    rules=None,
):
    resolver, binding_registry, template_registry = _build_context(bindings=bindings, templates=templates)

    kwargs = {"rules": rules} if rules is not None else {}

    service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityService(
        resolver,
        binding_registry,
        **kwargs,
    )

    return service, resolver, binding_registry, template_registry


class TestCompatibleTemplate:
    def test_compatible_template(self):
        service, *_ = _build_service()

        result = service.check("template-1")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityResult)
        assert result.compatible is True
        assert result.violations == ()


class TestConflictingBindings:
    def test_conflicting_capability_targets(self):
        service, *_ = _build_service(
            bindings=(
                ("binding-1", "profile-a", "capability-a"),
                ("binding-2", "profile-b", "capability-a"),
            ),
            templates=(("template-1", ("binding-1", "binding-2")),),
        )

        result = service.check("template-1")

        assert result.compatible is False
        assert any(v.rule_id == "unique_capability_targets" for v in result.violations)

    def test_empty_members(self):
        service, *_ = _build_service(
            bindings=(),
            templates=(("template-1", ()),),
        )

        result = service.check("template-1")

        assert result.compatible is False
        assert any(v.rule_id == "non_empty_members" for v in result.violations)


class TestSupports:
    def test_supports_true(self):
        service, *_ = _build_service()

        assert service.supports("template-1") is True

    def test_supports_false(self):
        service, *_ = _build_service(
            bindings=(
                ("binding-1", "profile-a", "capability-a"),
                ("binding-2", "profile-b", "capability-a"),
            ),
            templates=(("template-1", ("binding-1", "binding-2")),),
        )

        assert service.supports("template-1") is False


class TestMultipleViolationsCollected:
    def test_multiple_violations_collected(self):
        service, *_ = _build_service(
            bindings=(
                ("binding-1", "profile-a", "capability-a"),
                ("binding-2", "profile-a", "capability-a"),
            ),
            templates=(("template-1", ("binding-1", "binding-2")),),
        )

        result = service.check("template-1")

        assert result.compatible is False

        rule_ids = {v.rule_id for v in result.violations}

        assert "unique_capability_targets" in rule_ids
        assert "unique_profile_bindings" in rule_ids
        assert len(result.violations) >= 2


class TestDeterministicEvaluation:
    def test_deterministic_evaluation(self):
        service, *_ = _build_service()

        first = service.check("template-1")
        second = service.check("template-1")

        assert first.compatible == second.compatible
        assert first.violations == second.violations

    def test_rules_evaluated_in_declared_order(self):
        service, *_ = _build_service()

        assert [rule.rule_id for rule in service.rules()] == [
            "non_empty_members",
            "unique_capability_targets",
            "unique_profile_bindings",
        ]


class TestImmutableResult:
    def test_immutable_result(self):
        service, *_ = _build_service()

        result = service.check("template-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.compatible = False

    def test_immutable_violations(self):
        service, *_ = _build_service(
            bindings=(
                ("binding-1", "profile-a", "capability-a"),
                ("binding-2", "profile-b", "capability-a"),
            ),
            templates=(("template-1", ("binding-1", "binding-2")),),
        )

        result = service.check("template-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.violations[0].rule_id = "changed"


class TestValidate:
    def test_validate_raises_on_incompatible_template(self):
        service, _, binding_registry, _ = _build_service(
            bindings=(
                ("binding-1", "profile-a", "capability-a"),
                ("binding-2", "profile-b", "capability-a"),
            ),
            templates=(),
        )

        template = _template("template-1", binding_ids=("binding-1", "binding-2"))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError):
            service.validate(template)

    def test_validate_passes_on_compatible_template(self):
        service, *_ = _build_service(templates=())

        template = _template("template-1", binding_ids=("binding-1",))

        service.validate(template)

    def test_validate_none_template(self):
        service, *_ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError):
            service.validate(None)


class TestRejectInvalidIdentifiers:
    def test_reject_blank_template_id(self):
        service, *_ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError):
            service.check("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError):
            service.check(None)

    def test_reject_unknown_template(self):
        service, *_ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError):
            service.check("template-missing")


class TestRejectDuplicateRuleIds:
    def test_reject_duplicate_rule_ids(self):
        duplicate_rules = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityRule(
                rule_id="non_empty_members",
                severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilitySeverity.ERROR,
            ),
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityRule(
                rule_id="non_empty_members",
                severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilitySeverity.WARNING,
            ),
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError):
            _build_service(rules=duplicate_rules)
