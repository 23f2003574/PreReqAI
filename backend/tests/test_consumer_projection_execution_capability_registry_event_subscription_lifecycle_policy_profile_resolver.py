import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResultError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionSource,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError,
)


def _build_profile(profile_id, policy_identifiers=("policy-a",)):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,

        profile_name=profile_id,

        description=f"Profile {profile_id}.",

        policy_identifiers=policy_identifiers,
    )


def _build_registry(*profile_ids):
    registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()

    for profile_id in profile_ids:

        registry.register(
            _build_profile(
                profile_id
            )
        )

    return registry


class TestResolveExistingProfile:
    """A profile ID that is directly registered resolves to it."""

    def test_resolve_existing_profile(self):
        registry = _build_registry("development")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
            registry
        )

        result = resolver.resolve(
            "development"
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResult,
        )
        assert result.resolved is True
        assert result.resolution_source == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionSource.REGISTRY
        assert result.profile is registry.find("development")


class TestResolveMissingProfile:
    """A missing profile ID with no cache or default resolves unsuccessfully."""

    def test_resolve_missing_profile(self):
        registry = _build_registry("development")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
            registry
        )

        result = resolver.resolve(
            "does-not-exist"
        )

        assert result.resolved is False
        assert result.profile is None
        assert result.resolution_source is None


class TestResolveUsingCache:
    """A missing profile ID falls back to the cache when the registry has no match."""

    def test_resolve_using_cache(self):
        registry = _build_registry("development")
        cache = _build_registry("cached-profile")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
            registry,

            cache=cache,
        )

        result = resolver.resolve(
            "cached-profile"
        )

        assert result.resolved is True
        assert result.resolution_source == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionSource.CACHE
        assert result.profile is cache.find("cached-profile")


class TestResolveUsingDefault:
    """A missing profile ID falls back to the default profile when configured."""

    def test_resolve_using_default(self):
        registry = _build_registry("development")
        default_profile = _build_profile("fallback")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
            registry,

            default_profile=default_profile,
        )

        result = resolver.resolve(
            "does-not-exist"
        )

        assert result.resolved is True
        assert result.resolution_source == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionSource.DEFAULT
        assert result.profile is default_profile


class TestResolveOrRaiseSuccess:
    """resolve_or_raise() returns the resolved profile directly."""

    def test_resolve_or_raise_success(self):
        registry = _build_registry("development")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
            registry
        )

        resolved = resolver.resolve_or_raise(
            "development"
        )

        assert resolved is registry.find("development")


class TestResolveOrRaiseFailure:
    """resolve_or_raise() raises when no profile can be resolved."""

    def test_resolve_or_raise_failure(self):
        registry = _build_registry("development")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
            registry
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError
        ):
            resolver.resolve_or_raise(
                "does-not-exist"
            )


class TestCanResolveTrue:
    """can_resolve() reports True for a registered profile ID."""

    def test_can_resolve_true(self):
        registry = _build_registry("development")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
            registry
        )

        assert resolver.can_resolve(
            "development"
        ) is True


class TestCanResolveFalse:
    """can_resolve() reports False for an unregistered profile ID."""

    def test_can_resolve_false(self):
        registry = _build_registry("development")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
            registry
        )

        assert resolver.can_resolve(
            "does-not-exist"
        ) is False


class TestImmutableResult:
    """A resolution result cannot have its fields reassigned."""

    def test_immutable_result(self):
        registry = _build_registry("development")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
            registry
        )

        result = resolver.resolve(
            "development"
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.resolved = False

    def test_does_not_mutate_registry(self):
        registry = _build_registry("development")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
            registry
        )

        resolver.resolve(
            "does-not-exist"
        )

        assert [
            profile.profile_id
            for profile in registry.list()
        ] == ["development"]


class TestRejectNoneRegistry:
    """Constructing a resolver against a None registry is rejected."""

    def test_reject_none_registry(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
                None
            )


class TestRejectNoneProfileId:
    """Resolving a None profile ID is rejected."""

    def test_reject_none_profile_id(self):
        registry = _build_registry("development")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
            registry
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError
        ):
            resolver.resolve(
                None
            )


class TestRejectBlankProfileId:
    """Resolving a blank profile ID is rejected."""

    def test_reject_blank_profile_id(self):
        registry = _build_registry("development")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
            registry
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError
        ):
            resolver.resolve(
                "   "
            )


class TestRejectUnknownResolutionSource:
    """A resolved result carrying an unknown resolution source is rejected."""

    def test_reject_unknown_resolution_source(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResult(
                profile=_build_profile("development"),

                resolved=True,

                resolution_source="not-a-real-source",
            )


class TestRejectMalformedResolutionResult:
    """A resolved result missing a profile, or an unresolved result carrying one, is rejected."""

    def test_reject_resolved_without_profile(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResult(
                profile=None,

                resolved=True,

                resolution_source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionSource.REGISTRY,
            )

    def test_reject_unresolved_with_profile(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResult(
                profile=_build_profile("development"),

                resolved=False,

                resolution_source=None,
            )

    def test_reject_unresolved_with_source(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResult(
                profile=None,

                resolved=False,

                resolution_source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionSource.REGISTRY,
            )
