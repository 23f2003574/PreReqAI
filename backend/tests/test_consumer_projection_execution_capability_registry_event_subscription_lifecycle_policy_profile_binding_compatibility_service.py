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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityRule,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilitySeverity,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService,
)


class _CapabilityRegistry:
    def __init__(self, *capability_ids):
        self._capability_ids = set(capability_ids)

    def contains(self, capability_id):
        return capability_id in self._capability_ids


class _FakeProfileRegistry:
    """Bypasses the real Profile dataclass's own structural validation, so
    malformed policy identifier collections can reach the compatibility
    service's rule evaluation."""

    def __init__(self, profiles):
        self._profiles = profiles

    def contains(self, profile_id):
        return profile_id in self._profiles

    def find(self, profile_id):
        return self._profiles.get(profile_id)


def _build_profile(profile_id, policy_identifiers):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,
        profile_name=profile_id,
        description=f"Profile {profile_id}.",
        policy_identifiers=policy_identifiers,
    )


def _build_service(profiles=(("profile-a", ("capability-a",)),), capability_ids=("capability-a",), rules=None):
    profile_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()

    for profile_id, policy_identifiers in profiles:
        profile_service.register(_build_profile(profile_id, policy_identifiers))

    capability_registry = _CapabilityRegistry(*capability_ids)

    kwargs = {"rules": rules} if rules is not None else {}

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityService(
        profile_service,
        capability_registry,
        **kwargs,
    )


class TestCompatibleBinding:
    def test_compatible_binding(self):
        service = _build_service()

        result = service.check("profile-a", "capability-a")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityResult)
        assert result.compatible is True
        assert result.violations == ()


class TestIncompatibleBinding:
    def test_incompatible_binding_unsupported_capability(self):
        service = _build_service(
            profiles=(("profile-a", ("capability-x",)),),
            capability_ids=("capability-a", "capability-x"),
        )

        result = service.check("profile-a", "capability-a")

        assert result.compatible is False
        assert any(v.rule_id == "capability_supported" for v in result.violations)

    def test_incompatible_binding_empty_policy_identifiers(self):
        service = _build_service(profiles=(("profile-a", ()),))

        result = service.check("profile-a", "capability-a")

        assert result.compatible is False
        assert any(v.rule_id == "non_empty_policy_identifiers" for v in result.violations)


class TestSupports:
    def test_supports_true(self):
        service = _build_service()

        assert service.supports("profile-a", "capability-a") is True

    def test_supports_false(self):
        service = _build_service(
            profiles=(("profile-a", ("capability-x",)),),
            capability_ids=("capability-a", "capability-x"),
        )

        assert service.supports("profile-a", "capability-a") is False


class TestMultipleViolationsCollected:
    def test_multiple_violations_collected(self):
        profile_registry = _FakeProfileRegistry(
            {"profile-a": SimpleNamespace(profile_id="profile-a", policy_identifiers=("dup", "dup", "   "))}
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityService(
            profile_registry,
            _CapabilityRegistry("capability-a"),
        )

        result = service.check("profile-a", "capability-a")

        assert result.compatible is False

        rule_ids = {v.rule_id for v in result.violations}

        assert "unique_policy_identifiers" in rule_ids
        assert "no_blank_policy_identifiers" in rule_ids
        assert "capability_supported" in rule_ids
        assert len(result.violations) >= 3


class TestDeterministicEvaluation:
    def test_deterministic_evaluation(self):
        service = _build_service(profiles=(("profile-a", ()),))

        first = service.check("profile-a", "capability-a")
        second = service.check("profile-a", "capability-a")

        assert first.compatible == second.compatible
        assert first.violations == second.violations

    def test_rules_evaluated_in_declared_order(self):
        service = _build_service()

        assert [rule.rule_id for rule in service.list_rules()] == [
            "non_empty_policy_identifiers",
            "unique_policy_identifiers",
            "no_blank_policy_identifiers",
            "capability_supported",
        ]


class TestImmutableResult:
    def test_immutable_result(self):
        service = _build_service()

        result = service.check("profile-a", "capability-a")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.compatible = False

    def test_immutable_violations(self):
        service = _build_service(profiles=(("profile-a", ()),))

        result = service.check("profile-a", "capability-a")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.violations[0].rule_id = "changed"


class TestValidateRaisesOnIncompatibleBinding:
    def test_validate_raises_on_incompatible_binding(self):
        service = _build_service(profiles=(("profile-a", ()),))

        binding = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
            binding_id="binding-1",
            profile_id="profile-a",
            capability_id="capability-a",
            created_at=datetime.now(timezone.utc),
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError):
            service.validate(binding)

    def test_validate_none_binding(self):
        service = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError):
            service.validate(None)


class TestRejectInvalidIdentifiers:
    def test_reject_blank_profile_id(self):
        service = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError):
            service.check("   ", "capability-a")

    def test_reject_blank_capability_id(self):
        service = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError):
            service.check("profile-a", None)

    def test_reject_unknown_profile(self):
        service = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError):
            service.check("profile-missing", "capability-a")

    def test_reject_unknown_capability(self):
        service = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError):
            service.check("profile-a", "capability-missing")


class TestRejectDuplicateRuleIds:
    def test_reject_duplicate_rule_ids(self):
        duplicate_rules = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityRule(
                rule_id="non_empty_policy_identifiers",
                description="First.",
                severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilitySeverity.ERROR,
            ),
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityRule(
                rule_id="non_empty_policy_identifiers",
                description="Second.",
                severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilitySeverity.WARNING,
            ),
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError):
            _build_service(rules=duplicate_rules)
