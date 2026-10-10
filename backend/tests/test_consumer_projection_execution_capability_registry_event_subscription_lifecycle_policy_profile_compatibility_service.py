import dataclasses

from datetime import datetime, timezone

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityRule,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilitySeverity,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService,
)


def _build_profile(profile_id="development", policy_identifiers=("policy-a", "policy-b")):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,

        profile_name=profile_id,

        description=f"Profile {profile_id}.",

        policy_identifiers=policy_identifiers,
    )


def _build_version(version_id, policy_identifiers):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion(
        version=version_id,

        policy_identifiers=policy_identifiers,

        created_at=datetime.now(timezone.utc),
    )


def _build_service(profile_id="development", policy_identifiers=("policy-a", "policy-b"), versions=()):
    registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
    registry.register(
        _build_profile(

            profile_id,

            policy_identifiers,
        )
    )

    version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()

    for version_id, version_policy_identifiers in versions:

        version_service.publish(

            profile_id,

            _build_version(

                version_id,

                version_policy_identifiers,
            ),
        )

    resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
        registry
    )

    service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityService(
        resolver,

        version_service,
    )

    return service, registry, version_service


class TestCompatibleProfile:
    """A profile that passes every rule is compatible."""

    def test_compatible_profile(self):
        service, registry, _ = _build_service()

        result = service.check(
            registry.find("development")
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityResult,
        )
        assert result.compatible is True
        assert result.incompatibilities == ()


class TestIncompatibleProfile:
    """A profile grouping zero policy identifiers is incompatible."""

    def test_incompatible_profile(self):
        service, _, _ = _build_service(
            policy_identifiers=(),
        )

        result = service.check(
            _build_profile(
                policy_identifiers=(),
            )
        )

        assert result.compatible is False
        assert any(
            incompatibility.rule_id == "non_empty_policy_identifiers"
            for incompatibility
            in result.incompatibilities
        )


class TestVersionCompatibility:
    """check_version() evaluates the identifiers of the requested version, not the profile's own."""

    def test_version_compatibility_success(self):
        service, _, _ = _build_service(
            versions=(
                ("1.0.0", ("policy-a",)),
            ),
        )

        result = service.check_version(
            "development",

            "1.0.0",
        )

        assert result.compatible is True

    def test_version_compatibility_failure(self):
        service, _, _ = _build_service(
            versions=(
                ("1.0.0", ()),
            ),
        )

        result = service.check_version(
            "development",

            "1.0.0",
        )

        assert result.compatible is False
        assert any(
            incompatibility.rule_id == "non_empty_policy_identifiers"
            for incompatibility
            in result.incompatibilities
        )


class TestCapabilitySupport:
    """supports() reports whether a capability is grouped under a profile."""

    def test_supports_true(self):
        service, registry, _ = _build_service()

        assert service.supports(
            registry.find("development"),

            "policy-a",
        ) is True

    def test_supports_false(self):
        service, registry, _ = _build_service()

        assert service.supports(
            registry.find("development"),

            "policy-z",
        ) is False


class TestMultipleIncompatibilitiesCollected:
    """Every failing rule is reported, not just the first."""

    def test_multiple_incompatibilities_collected(self):
        service, _, _ = _build_service(
            versions=(
                ("1.0.0", ("", "policy-a", "policy-a")),
            ),
        )

        result = service.check_version(
            "development",

            "1.0.0",
        )

        assert result.compatible is False
        assert {
            incompatibility.rule_id
            for incompatibility
            in result.incompatibilities
        } == {
            "unique_policy_identifiers",
            "no_blank_policy_identifiers",
        }


class TestDeterministicEvaluationOrder:
    """Rules are always evaluated, and reported, in declared order."""

    def test_deterministic_evaluation_order(self):
        service, _, _ = _build_service(
            versions=(
                ("1.0.0", ("", "policy-a", "policy-a")),
            ),
        )

        first_result = service.check_version("development", "1.0.0")
        second_result = service.check_version("development", "1.0.0")

        assert [
            incompatibility.rule_id
            for incompatibility
            in first_result.incompatibilities
        ] == [
            incompatibility.rule_id
            for incompatibility
            in second_result.incompatibilities
        ]


class TestImmutableCompatibilityResult:
    """A compatibility result cannot have its fields reassigned."""

    def test_immutable_compatibility_result(self):
        service, registry, _ = _build_service()

        result = service.check(
            registry.find("development")
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.compatible = False

    def test_does_not_mutate_registry(self):
        service, registry, _ = _build_service()

        service.check(
            registry.find("development")
        )

        assert registry.find("development").policy_identifiers == ("policy-a", "policy-b")


class TestRejectInvalidInputs:
    """None inputs, blank identifiers, missing profiles/versions, and malformed rules are rejected."""

    def test_reject_none_profile(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError
        ):
            service.check(None)

    def test_reject_blank_profile_id(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError
        ):
            service.check_version("   ", "1.0.0")

    def test_reject_missing_profile(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError
        ):
            service.check_version("does-not-exist", "1.0.0")

    def test_reject_missing_version(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError
        ):
            service.check_version("development", "9.9.9")

    def test_reject_none_rule(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
        version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
            registry
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityService(
                resolver,

                version_service,

                rules=(None,),
            )

    def test_reject_duplicate_rule_ids(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
        version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
            registry
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityService(
                resolver,

                version_service,

                rules=(
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityRule(
                        rule_id="non_empty_policy_identifiers",

                        description="Duplicate one.",

                        severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilitySeverity.ERROR,
                    ),
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityRule(
                        rule_id="non_empty_policy_identifiers",

                        description="Duplicate two.",

                        severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilitySeverity.WARNING,
                    ),
                ),
            )

    def test_reject_malformed_rule(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
        version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
            registry
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityService(
                resolver,

                version_service,

                rules=(
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityRule(
                        rule_id="not_a_real_rule",

                        description="Not real.",

                        severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilitySeverity.ERROR,
                    ),
                ),
            )
