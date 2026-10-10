import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService,
)


def _build_policy(initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        ),
        initial_state,
    )


def _build_template(template_id, policy=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
        template_id=template_id,

        template_name=template_id,

        description=f"Template {template_id}.",

        lifecycle_policy=(
            policy
            if policy is not None
            else _build_policy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            )
        ),
    )


def _build_registry(*templates):
    registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()

    for template in templates:

        registry.register(
            template
        )

    return registry


class TestInstantiateValidTemplate:
    """A valid template can be instantiated into a new lifecycle policy."""

    def test_instantiate_valid_template(self):
        policy = _build_policy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
        )
        registry = _build_registry(
            _build_template(
                "standard-registration",
                policy=policy,
            )
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationService()
        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest(
            template_id="standard-registration",

            instance_identifier="instance-1",
        )

        result = service.instantiate(

            request,

            registry,
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationResult,
        )
        assert isinstance(
            result.lifecycle_policy,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
        )
        assert result.template_id == "standard-registration"
        assert result.lifecycle_policy == policy
        assert result.lifecycle_policy is not policy


class TestInstantiateMultipleInstances:
    """Multiple instances can be instantiated from the same template."""

    def test_instantiate_multiple_instances(self):
        registry = _build_registry(
            _build_template("standard-registration")
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationService()

        first = service.instantiate(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest(
                template_id="standard-registration",

                instance_identifier="instance-1",
            ),

            registry,
        )
        second = service.instantiate(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest(
                template_id="standard-registration",

                instance_identifier="instance-2",
            ),

            registry,
        )

        assert first.template_id == "standard-registration"
        assert second.template_id == "standard-registration"


class TestGeneratedInstancesAreIndependent:
    """Instances instantiated from the same template do not share state."""

    def test_generated_instances_are_independent(self):
        registry = _build_registry(
            _build_template("standard-registration")
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationService()

        first = service.instantiate(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest(
                template_id="standard-registration",

                instance_identifier="instance-1",
            ),

            registry,
        )
        second = service.instantiate(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest(
                template_id="standard-registration",

                instance_identifier="instance-2",
            ),

            registry,
        )

        assert first.lifecycle_policy is not second.lifecycle_policy
        assert first.lifecycle_policy == second.lifecycle_policy


class TestMissingTemplate:
    """Instantiating from a template ID that is not registered is rejected."""

    def test_missing_template(self):
        registry = _build_registry(
            _build_template("standard-registration")
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError
        ):
            service.instantiate(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest(
                    template_id="does-not-exist",

                    instance_identifier="instance-1",
                ),

                registry,
            )


class TestDuplicateInstanceIdentifier:
    """Reusing an instance identifier already instantiated is rejected."""

    def test_duplicate_instance_identifier(self):
        registry = _build_registry(
            _build_template("standard-registration")
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationService()
        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest(
            template_id="standard-registration",

            instance_identifier="instance-1",
        )

        service.instantiate(
            request,

            registry,
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError
        ):
            service.instantiate(
                request,

                registry,
            )


class TestImmutableRegistryAndTemplate:
    """Instantiation never mutates the resolved template or registry."""

    def test_immutable_registry_and_template(self):
        template = _build_template("standard-registration")
        registry = _build_registry(template)
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationService()

        service.instantiate(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest(
                template_id="standard-registration",

                instance_identifier="instance-1",
            ),

            registry,
        )

        assert registry.find("standard-registration") is template
        assert [
            found.template_id
            for found in registry.list()
        ] == ["standard-registration"]

        with pytest.raises(dataclasses.FrozenInstanceError):
            template.template_id = "changed"


class TestRejectInvalidRequest:
    """Invalid requests, templates, and inputs are rejected."""

    def test_reject_none_request(self):
        registry = _build_registry(
            _build_template("standard-registration")
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError
        ):
            service.instantiate(
                None,

                registry,
            )

    def test_reject_none_registry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError
        ):
            service.instantiate(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest(
                    template_id="standard-registration",

                    instance_identifier="instance-1",
                ),

                None,
            )

    def test_reject_blank_template_id(self):
        registry = _build_registry(
            _build_template("standard-registration")
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError
        ):
            service.instantiate(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest(
                    template_id="   ",

                    instance_identifier="instance-1",
                ),

                registry,
            )

    def test_reject_blank_instance_identifier(self):
        registry = _build_registry(
            _build_template("standard-registration")
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError
        ):
            service.instantiate(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest(
                    template_id="standard-registration",

                    instance_identifier="   ",
                ),

                registry,
            )

    def test_reject_invalid_template(self):
        invalid_template = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
            template_id="broken-template",

            template_name="",

            description="",

            lifecycle_policy=None,
        )
        registry = _build_registry(
            invalid_template
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError
        ):
            service.instantiate(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest(
                    template_id="broken-template",

                    instance_identifier="instance-1",
                ),

                registry,
            )

    def test_instantiate_or_raise_behaves_the_same(self):
        registry = _build_registry(
            _build_template("standard-registration")
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationService()

        result = service.instantiate_or_raise(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest(
                template_id="standard-registration",

                instance_identifier="instance-1",
            ),

            registry,
        )

        assert result.template_id == "standard-registration"

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError
        ):
            service.instantiate_or_raise(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest(
                    template_id="does-not-exist",

                    instance_identifier="instance-2",
                ),

                registry,
            )
