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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResultError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionSource,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError,
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


def _template(template_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
        template_id=template_id,
        name=template_id,
        binding_ids=binding_ids,
        metadata={},
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

    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

    return template_registry, binding_registry, activation_service


class TestProfileBindingTemplateResolver:
    def test_resolve_existing_template(self):
        template_registry, binding_registry, activation_service = _build_context()
        template_registry.register(_template("template-1", binding_ids=("binding-1", "binding-2")))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
            template_registry, binding_registry, activation_service
        )

        result = resolver.resolve("template-1")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResult)
        assert result.resolved is True
        assert result.template == template_registry.find("template-1")
        assert result.bindings == (binding_registry.find("binding-1"), binding_registry.find("binding-2"))
        assert result.source == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionSource.REGISTRY

    def test_resolve_missing_template(self):
        template_registry, binding_registry, activation_service = _build_context()

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
            template_registry, binding_registry, activation_service
        )

        result = resolver.resolve("template-does-not-exist")

        assert result.resolved is False
        assert result.template is None
        assert result.bindings == ()
        assert result.source is None

    def test_resolve_missing_uses_default(self):
        template_registry, binding_registry, activation_service = _build_context()
        default_template = _template("template-default", binding_ids=("binding-1",))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
            template_registry,
            binding_registry,
            activation_service,
            default_template=default_template,
        )

        result = resolver.resolve("template-does-not-exist")

        assert result.resolved is True
        assert result.template is default_template
        assert result.bindings == (binding_registry.find("binding-1"),)
        assert result.source == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionSource.DEFAULT

    def test_resolve_active_members_only(self):
        template_registry, binding_registry, activation_service = _build_context(
            binding_ids=("binding-1", "binding-2", "binding-3"),
            active_binding_ids=("binding-1", "binding-3"),
        )
        template_registry.register(_template("template-1", binding_ids=("binding-1", "binding-2", "binding-3")))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
            template_registry, binding_registry, activation_service
        )

        result = resolver.resolve("template-1")

        assert result.bindings == (binding_registry.find("binding-1"), binding_registry.find("binding-3"))

    def test_ignore_inactive_and_missing_members(self):
        template_registry, binding_registry, activation_service = _build_context(
            binding_ids=("binding-1", "binding-2"),
            active_binding_ids=("binding-1",),
        )
        template_registry.register(
            _template("template-1", binding_ids=("binding-1", "binding-2", "binding-missing"))
        )

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
            template_registry, binding_registry, activation_service
        )

        result = resolver.resolve("template-1")

        assert result.bindings == (binding_registry.find("binding-1"),)

    def test_resolve_or_raise_success(self):
        template_registry, binding_registry, activation_service = _build_context()
        template = _template("template-1", binding_ids=("binding-1",))
        template_registry.register(template)

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
            template_registry, binding_registry, activation_service
        )

        assert resolver.resolve_or_raise("template-1") == template

    def test_resolve_or_raise_failure(self):
        template_registry, binding_registry, activation_service = _build_context()

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
            template_registry, binding_registry, activation_service
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError):
            resolver.resolve_or_raise("template-does-not-exist")

    def test_contains_true_and_false(self):
        template_registry, binding_registry, activation_service = _build_context()
        template_registry.register(_template("template-1", binding_ids=("binding-1",)))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
            template_registry, binding_registry, activation_service
        )

        assert resolver.contains("template-1") is True
        assert resolver.contains("template-does-not-exist") is False

    def test_resolve_bindings(self):
        template_registry, binding_registry, activation_service = _build_context(
            binding_ids=("binding-1", "binding-2"),
            active_binding_ids=("binding-1", "binding-2"),
        )
        template_registry.register(_template("template-1", binding_ids=("binding-2", "binding-1")))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
            template_registry, binding_registry, activation_service
        )

        assert resolver.resolve_bindings("template-1") == (binding_registry.find("binding-2"), binding_registry.find("binding-1"))
        assert resolver.resolve_bindings("template-does-not-exist") == ()

    def test_immutable_result(self):
        template_registry, binding_registry, activation_service = _build_context()
        template_registry.register(_template("template-1", binding_ids=("binding-1",)))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
            template_registry, binding_registry, activation_service
        )

        result = resolver.resolve("template-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.resolved = False

    def test_does_not_mutate_registries(self):
        template_registry, binding_registry, activation_service = _build_context()
        template_registry.register(_template("template-1", binding_ids=("binding-1",)))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
            template_registry, binding_registry, activation_service
        )

        resolver.resolve("template-1")
        resolver.resolve("template-does-not-exist")

        assert len(template_registry.list()) == 1
        assert len(binding_registry.list()) == 3

    def test_reject_none_dependencies(self):
        template_registry, binding_registry, activation_service = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
                None, binding_registry, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
                template_registry, None, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
                template_registry, binding_registry, None
            )

    def test_reject_blank_template_id(self):
        template_registry, binding_registry, activation_service = _build_context()

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
            template_registry, binding_registry, activation_service
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError):
            resolver.resolve("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError):
            resolver.resolve(None)

    def test_reject_corrupted_template_membership(self):
        template_registry, binding_registry, activation_service = _build_context()

        class CorruptedRegistry:
            def find(self, template_id):
                return object()

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver(
            CorruptedRegistry(), binding_registry, activation_service
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError):
            resolver.resolve("template-1")

    def test_reject_invalid_resolution_source(self):
        template = _template("template-1", binding_ids=("binding-1",))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResult(
                template=template,
                bindings=(),
                resolved=True,
                source="not-a-real-source",
            )

    def test_reject_malformed_result(self):
        template = _template("template-1", binding_ids=("binding-1",))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResult(
                template=None,
                bindings=(),
                resolved=True,
                source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionSource.REGISTRY,
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResult(
                template=template,
                bindings=(),
                resolved=False,
                source=None,
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResult(
                template=None,
                bindings=(),
                resolved=False,
                source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionSource.REGISTRY,
            )
