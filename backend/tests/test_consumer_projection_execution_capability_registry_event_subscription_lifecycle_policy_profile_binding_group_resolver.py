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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResultError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionSource,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
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
        capability_id=f"capability-{binding_id}",
        created_at=datetime.now(timezone.utc),
    )


def _group(group_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
        group_id=group_id,
        group_name=group_id,
        binding_ids=binding_ids,
    )


def _build_context(binding_ids=("binding-1", "binding-2", "binding-3"), active_binding_ids=None):
    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

    for binding_id in binding_ids:
        binding_registry.register(_binding(binding_id))

    activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(
        binding_registry,
        FakeClock(datetime.now(timezone.utc)),
    )

    for binding_id in active_binding_ids if active_binding_ids is not None else binding_ids:
        activation_service.activate(binding_id)

    group_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

    return group_registry, binding_registry, activation_service


class TestProfileBindingGroupResolver:
    def test_resolve_existing_group(self):
        group_registry, binding_registry, activation_service = _build_context()
        group_registry.register(_group("group-1", binding_ids=("binding-1", "binding-2")))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
            group_registry, binding_registry, activation_service
        )

        result = resolver.resolve("group-1")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResult)
        assert result.resolved is True
        assert result.group == group_registry.find("group-1")
        assert result.bindings == (binding_registry.find("binding-1"), binding_registry.find("binding-2"))
        assert result.source == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionSource.REGISTRY

    def test_resolve_missing_group(self):
        group_registry, binding_registry, activation_service = _build_context()

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
            group_registry, binding_registry, activation_service
        )

        result = resolver.resolve("group-does-not-exist")

        assert result.resolved is False
        assert result.group is None
        assert result.bindings == ()
        assert result.source is None

    def test_resolve_missing_uses_default(self):
        group_registry, binding_registry, activation_service = _build_context()
        default_group = _group("group-default", binding_ids=("binding-1",))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
            group_registry,
            binding_registry,
            activation_service,
            default_group=default_group,
        )

        result = resolver.resolve("group-does-not-exist")

        assert result.resolved is True
        assert result.group is default_group
        assert result.bindings == (binding_registry.find("binding-1"),)
        assert result.source == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionSource.DEFAULT

    def test_resolve_active_members_only(self):
        group_registry, binding_registry, activation_service = _build_context(
            binding_ids=("binding-1", "binding-2", "binding-3"),
            active_binding_ids=("binding-1", "binding-3"),
        )
        group_registry.register(_group("group-1", binding_ids=("binding-1", "binding-2", "binding-3")))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
            group_registry, binding_registry, activation_service
        )

        result = resolver.resolve("group-1")

        assert result.bindings == (binding_registry.find("binding-1"), binding_registry.find("binding-3"))

    def test_ignore_inactive_and_missing_members(self):
        group_registry, binding_registry, activation_service = _build_context(
            binding_ids=("binding-1", "binding-2"),
            active_binding_ids=("binding-1",),
        )
        group_registry.register(
            _group("group-1", binding_ids=("binding-1", "binding-2", "binding-missing"))
        )

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
            group_registry, binding_registry, activation_service
        )

        result = resolver.resolve("group-1")

        assert result.bindings == (binding_registry.find("binding-1"),)

    def test_resolve_or_raise_success(self):
        group_registry, binding_registry, activation_service = _build_context()
        group = _group("group-1", binding_ids=("binding-1",))
        group_registry.register(group)

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
            group_registry, binding_registry, activation_service
        )

        assert resolver.resolve_or_raise("group-1") == group

    def test_resolve_or_raise_failure(self):
        group_registry, binding_registry, activation_service = _build_context()

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
            group_registry, binding_registry, activation_service
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError):
            resolver.resolve_or_raise("group-does-not-exist")

    def test_contains_true_and_false(self):
        group_registry, binding_registry, activation_service = _build_context()
        group_registry.register(_group("group-1", binding_ids=("binding-1",)))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
            group_registry, binding_registry, activation_service
        )

        assert resolver.contains("group-1") is True
        assert resolver.contains("group-does-not-exist") is False

    def test_resolve_bindings(self):
        group_registry, binding_registry, activation_service = _build_context(
            binding_ids=("binding-1", "binding-2"),
            active_binding_ids=("binding-1", "binding-2"),
        )
        group_registry.register(_group("group-1", binding_ids=("binding-2", "binding-1")))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
            group_registry, binding_registry, activation_service
        )

        assert resolver.resolve_bindings("group-1") == (binding_registry.find("binding-2"), binding_registry.find("binding-1"))
        assert resolver.resolve_bindings("group-does-not-exist") == ()

    def test_immutable_result(self):
        group_registry, binding_registry, activation_service = _build_context()
        group_registry.register(_group("group-1", binding_ids=("binding-1",)))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
            group_registry, binding_registry, activation_service
        )

        result = resolver.resolve("group-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.resolved = False

    def test_does_not_mutate_registries(self):
        group_registry, binding_registry, activation_service = _build_context()
        group_registry.register(_group("group-1", binding_ids=("binding-1",)))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
            group_registry, binding_registry, activation_service
        )

        resolver.resolve("group-1")
        resolver.resolve("group-does-not-exist")

        assert len(group_registry.list()) == 1
        assert len(binding_registry.list()) == 3

    def test_reject_none_dependencies(self):
        group_registry, binding_registry, activation_service = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
                None, binding_registry, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
                group_registry, None, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
                group_registry, binding_registry, None
            )

    def test_reject_blank_group_id(self):
        group_registry, binding_registry, activation_service = _build_context()

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
            group_registry, binding_registry, activation_service
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError):
            resolver.resolve("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError):
            resolver.resolve(None)

    def test_reject_corrupted_group_membership(self):
        group_registry, binding_registry, activation_service = _build_context()

        class CorruptedRegistry:
            def find(self, group_id):
                return object()

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver(
            CorruptedRegistry(), binding_registry, activation_service
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError):
            resolver.resolve("group-1")

    def test_reject_invalid_resolution_source(self):
        group_registry, binding_registry, activation_service = _build_context()
        group = _group("group-1", binding_ids=("binding-1",))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResult(
                group=group,
                bindings=(),
                resolved=True,
                source="not-a-real-source",
            )

    def test_reject_malformed_result(self):
        group = _group("group-1", binding_ids=("binding-1",))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResult(
                group=None,
                bindings=(),
                resolved=True,
                source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionSource.REGISTRY,
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResult(
                group=group,
                bindings=(),
                resolved=False,
                source=None,
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResult(
                group=None,
                bindings=(),
                resolved=False,
                source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionSource.REGISTRY,
            )
