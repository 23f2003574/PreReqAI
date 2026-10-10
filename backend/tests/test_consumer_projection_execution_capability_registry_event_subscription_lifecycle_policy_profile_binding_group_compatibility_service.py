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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityRule,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilitySeverity,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
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


def _group(group_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
        group_id=group_id,
        group_name=group_id,
        binding_ids=binding_ids,
    )


def _build_context(bindings=(("binding-1", "profile-a", "capability-a"),), groups=()):
    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

    activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(
        binding_registry,
        FakeClock(datetime.now(timezone.utc)),
    )

    for binding_id, profile_id, capability_id in bindings:
        binding_registry.register(_binding(binding_id, profile_id, capability_id))
        activation_service.activate(binding_id)

    group_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

    for group_id, binding_ids in groups:
        group_registry.register(_group(group_id, binding_ids=binding_ids))

    resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
        group_registry, binding_registry, activation_service
    )

    return resolver, binding_registry, group_registry


def _build_service(bindings=(("binding-1", "profile-a", "capability-a"),), groups=(("group-1", ("binding-1",)),), rules=None):
    resolver, binding_registry, group_registry = _build_context(bindings=bindings, groups=groups)

    kwargs = {"rules": rules} if rules is not None else {}

    service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityService(
        resolver,
        binding_registry,
        **kwargs,
    )

    return service, resolver, binding_registry, group_registry


class TestCompatibleGroup:
    def test_compatible_group(self):
        service, *_ = _build_service()

        result = service.check("group-1")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityResult)
        assert result.compatible is True
        assert result.violations == ()


class TestConflictingBindings:
    def test_conflicting_capability_targets(self):
        service, *_ = _build_service(
            bindings=(
                ("binding-1", "profile-a", "capability-a"),
                ("binding-2", "profile-b", "capability-a"),
            ),
            groups=(("group-1", ("binding-1", "binding-2")),),
        )

        result = service.check("group-1")

        assert result.compatible is False
        assert any(v.rule_id == "unique_capability_targets" for v in result.violations)

    def test_empty_members(self):
        service, *_ = _build_service(
            bindings=(),
            groups=(("group-1", ()),),
        )

        result = service.check("group-1")

        assert result.compatible is False
        assert any(v.rule_id == "non_empty_members" for v in result.violations)


class TestSupports:
    def test_supports_true(self):
        service, *_ = _build_service()

        assert service.supports("group-1") is True

    def test_supports_false(self):
        service, *_ = _build_service(
            bindings=(
                ("binding-1", "profile-a", "capability-a"),
                ("binding-2", "profile-b", "capability-a"),
            ),
            groups=(("group-1", ("binding-1", "binding-2")),),
        )

        assert service.supports("group-1") is False


class TestMultipleViolationsCollected:
    def test_multiple_violations_collected(self):
        service, *_ = _build_service(
            bindings=(
                ("binding-1", "profile-a", "capability-a"),
                ("binding-2", "profile-a", "capability-a"),
            ),
            groups=(("group-1", ("binding-1", "binding-2")),),
        )

        result = service.check("group-1")

        assert result.compatible is False

        rule_ids = {v.rule_id for v in result.violations}

        assert "unique_capability_targets" in rule_ids
        assert "unique_profile_bindings" in rule_ids
        assert len(result.violations) >= 2


class TestDeterministicEvaluation:
    def test_deterministic_evaluation(self):
        service, *_ = _build_service()

        first = service.check("group-1")
        second = service.check("group-1")

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

        result = service.check("group-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.compatible = False

    def test_immutable_violations(self):
        service, *_ = _build_service(
            bindings=(
                ("binding-1", "profile-a", "capability-a"),
                ("binding-2", "profile-b", "capability-a"),
            ),
            groups=(("group-1", ("binding-1", "binding-2")),),
        )

        result = service.check("group-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.violations[0].rule_id = "changed"


class TestValidate:
    def test_validate_raises_on_incompatible_group(self):
        service, _, binding_registry, _ = _build_service(
            bindings=(
                ("binding-1", "profile-a", "capability-a"),
                ("binding-2", "profile-b", "capability-a"),
            ),
            groups=(),
        )

        group = _group("group-1", binding_ids=("binding-1", "binding-2"))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError):
            service.validate(group)

    def test_validate_passes_on_compatible_group(self):
        service, *_ = _build_service(groups=())

        group = _group("group-1", binding_ids=("binding-1",))

        service.validate(group)

    def test_validate_none_group(self):
        service, *_ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError):
            service.validate(None)


class TestRejectInvalidIdentifiers:
    def test_reject_blank_group_id(self):
        service, *_ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError):
            service.check("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError):
            service.check(None)

    def test_reject_unknown_group(self):
        service, *_ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError):
            service.check("group-missing")


class TestRejectDuplicateRuleIds:
    def test_reject_duplicate_rule_ids(self):
        duplicate_rules = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityRule(
                rule_id="non_empty_members",
                severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilitySeverity.ERROR,
            ),
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityRule(
                rule_id="non_empty_members",
                severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilitySeverity.WARNING,
            ),
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError):
            _build_service(rules=duplicate_rules)
