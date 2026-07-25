import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionSource,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError,
)


def _build_policy(initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        ),
        initial_state,
    )


def _build_template(template_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
        template_id=template_id,

        template_name=template_id,

        description=f"Template {template_id}.",

        lifecycle_policy=_build_policy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
        ),
    )


def _build_registry(*template_ids):
    registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()

    for template_id in template_ids:

        registry.register(
            _build_template(
                template_id
            )
        )

    return registry


class TestResolveDirectMatch:
    """A template ID that is directly registered resolves to it."""

    def test_resolve_direct_match(self):
        registry = _build_registry("standard-registration")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver()

        result = resolver.resolve(
            "standard-registration",

            registry,
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionResult,
        )
        assert result.resolution_successful is True
        assert result.resolution_source == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionSource.DIRECT_MATCH
        assert result.resolved_template is registry.find("standard-registration")


class TestResolveUsingDefaultTemplate:
    """A missing template ID falls back to the default template ID."""

    def test_resolve_using_default_template(self):
        registry = _build_registry("fallback-template")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver()

        result = resolver.resolve(
            "does-not-exist",

            registry,

            default_template_id="fallback-template",
        )

        assert result.resolution_successful is True
        assert result.resolution_source == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionSource.DEFAULT_TEMPLATE
        assert result.resolved_template is registry.find("fallback-template")


class TestResolveMissingTemplate:
    """A missing template ID with no default resolves unsuccessfully."""

    def test_resolve_missing_template(self):
        registry = _build_registry("standard-registration")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver()

        result = resolver.resolve(
            "does-not-exist",

            registry,
        )

        assert result.resolution_successful is False
        assert result.resolved_template is None
        assert result.resolution_source is None


class TestResolveMissingDefaultTemplate:
    """A default template ID that is not registered is rejected."""

    def test_resolve_missing_default_template(self):
        registry = _build_registry("standard-registration")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError
        ):
            resolver.resolve(
                "does-not-exist",

                registry,

                default_template_id="also-does-not-exist",
            )


class TestResolveOrRaiseSuccess:
    """resolve_or_raise() returns the resolved template directly."""

    def test_resolve_or_raise_success(self):
        registry = _build_registry("standard-registration")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver()

        resolved = resolver.resolve_or_raise(
            "standard-registration",

            registry,
        )

        assert resolved is registry.find("standard-registration")


class TestResolveOrRaiseFailure:
    """resolve_or_raise() raises when no template can be resolved."""

    def test_resolve_or_raise_failure(self):
        registry = _build_registry("standard-registration")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError
        ):
            resolver.resolve_or_raise(
                "does-not-exist",

                registry,
            )


class TestCanResolveTrue:
    """can_resolve() reports True for a registered template ID."""

    def test_can_resolve_true(self):
        registry = _build_registry("standard-registration")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver()

        assert resolver.can_resolve(
            "standard-registration",

            registry,
        ) is True


class TestCanResolveFalse:
    """can_resolve() reports False for an unregistered template ID."""

    def test_can_resolve_false(self):
        registry = _build_registry("standard-registration")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver()

        assert resolver.can_resolve(
            "does-not-exist",

            registry,
        ) is False


class TestImmutableResult:
    """A resolution result cannot have its fields reassigned."""

    def test_immutable_result(self):
        registry = _build_registry("standard-registration")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver()

        result = resolver.resolve(
            "standard-registration",

            registry,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.resolution_successful = False

    def test_does_not_mutate_registry(self):
        registry = _build_registry("standard-registration")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver()

        resolver.resolve(
            "does-not-exist",

            registry,

            default_template_id="standard-registration",
        )

        assert [
            template.template_id
            for template in registry.list()
        ] == ["standard-registration"]


class TestRejectNoneRegistry:
    """Resolving against a None registry is rejected."""

    def test_reject_none_registry(self):
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError
        ):
            resolver.resolve(
                "standard-registration",

                None,
            )


class TestRejectBlankTemplateId:
    """Resolving a blank template ID is rejected."""

    def test_reject_blank_template_id(self):
        registry = _build_registry("standard-registration")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError
        ):
            resolver.resolve(
                "   ",

                registry,
            )


class TestRejectBlankDefaultTemplateId:
    """Resolving with a blank default template ID is rejected."""

    def test_reject_blank_default_template_id(self):
        registry = _build_registry("standard-registration")
        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError
        ):
            resolver.resolve(
                "does-not-exist",

                registry,

                default_template_id="   ",
            )
