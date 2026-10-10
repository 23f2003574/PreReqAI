import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResultError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionSource,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolverError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService,
)


def _build_profile(profile_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,
        profile_name=profile_id,
        description=f"Profile {profile_id}.",
        policy_identifiers=(f"policy-{profile_id}",),
    )


def _build_registry(*profile_capability_pairs):
    profile_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()
    binding_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingService(profile_service)

    for profile_id, capability_id in profile_capability_pairs:
        if not profile_service.contains(profile_id):
            profile_service.register(_build_profile(profile_id))

        binding_service.bind(profile_id, capability_id)

    return binding_service


class TestProfileBindingResolver:
    def test_resolve_existing_binding(self):
        registry = _build_registry(("development", "capability-1"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolver(registry)

        result = resolver.resolve("capability-1")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResult)
        assert result.resolved is True
        assert result.capability_id == "capability-1"
        assert result.binding == registry.find_by_capability("capability-1").bindings[0]
        assert result.source == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionSource.REGISTRY

    def test_resolve_missing_binding(self):
        registry = _build_registry(("development", "capability-1"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolver(registry)

        result = resolver.resolve("capability-does-not-exist")

        assert result.resolved is False
        assert result.capability_id == "capability-does-not-exist"
        assert result.binding is None
        assert result.source is None

    def test_resolve_missing_uses_default(self):
        registry = _build_registry(("development", "capability-1"))
        default_binding = registry.bind("development", "capability-default")

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolver(
            registry,
            default_binding=default_binding,
        )

        result = resolver.resolve("capability-does-not-exist")

        assert result.resolved is True
        assert result.binding is default_binding
        assert result.source == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionSource.DEFAULT

    def test_resolve_or_raise_success(self):
        registry = _build_registry(("development", "capability-1"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolver(registry)

        resolved = resolver.resolve_or_raise("capability-1")

        assert resolved == registry.find_by_capability("capability-1").bindings[0]

    def test_resolve_or_raise_failure(self):
        registry = _build_registry(("development", "capability-1"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolver(registry)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolverError):
            resolver.resolve_or_raise("capability-does-not-exist")

    def test_can_resolve_true_and_false(self):
        registry = _build_registry(("development", "capability-1"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolver(registry)

        assert resolver.can_resolve("capability-1") is True
        assert resolver.can_resolve("capability-does-not-exist") is False

    def test_deterministic_resolution(self):
        registry = _build_registry(
            ("development", "capability-1"),
            ("staging", "capability-1"),
        )
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolver(registry)

        first = resolver.resolve("capability-1")
        second = resolver.resolve("capability-1")

        assert first.binding == second.binding
        assert first.binding.profile_id == "development"

    def test_immutable_result(self):
        registry = _build_registry(("development", "capability-1"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolver(registry)

        result = resolver.resolve("capability-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.resolved = False

    def test_does_not_mutate_registry(self):
        registry = _build_registry(("development", "capability-1"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolver(registry)

        resolver.resolve("capability-does-not-exist")

        assert len(registry.list().bindings) == 1

    def test_reject_none_registry(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolverError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolver(None)

    def test_reject_blank_capability_id(self):
        registry = _build_registry(("development", "capability-1"))
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolver(registry)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolverError):
            resolver.resolve("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolverError):
            resolver.resolve(None)

    def test_reject_invalid_resolution_source(self):
        registry = _build_registry(("development", "capability-1"))
        binding = registry.find_by_capability("capability-1").bindings[0]

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResult(
                capability_id="capability-1",
                binding=binding,
                resolved=True,
                source="not-a-real-source",
            )

    def test_reject_malformed_result(self):
        binding_registry = _build_registry(("development", "capability-1"))
        binding = binding_registry.find_by_capability("capability-1").bindings[0]

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResult(
                capability_id="capability-1",
                binding=None,
                resolved=True,
                source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionSource.REGISTRY,
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResult(
                capability_id="capability-1",
                binding=binding,
                resolved=False,
                source=None,
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResult(
                capability_id="capability-1",
                binding=None,
                resolved=False,
                source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionSource.REGISTRY,
            )
