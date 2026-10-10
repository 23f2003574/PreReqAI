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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionService,
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


def _build_context(binding_ids=("binding-1", "binding-2"), template_binding_ids=("binding-1", "binding-2")):
    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

    for binding_id in binding_ids:
        binding_registry.register(_binding(binding_id))

    activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(
        binding_registry,
        FakeClock(datetime.now(timezone.utc)),
    )

    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()
    template_registry.register(_template("template-1", binding_ids=template_binding_ids))

    parameterization_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationService(
        template_registry,
        {},
    )

    template_version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionService(
        template_registry,
        parameterization_service,
    )

    deployment_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentService(
        template_version_service,
        binding_registry,
        activation_service,
    )

    return deployment_service, template_version_service, template_registry, binding_registry, activation_service


def _request(template_id="template-1", version="v1", target_environment="production", parameter_values=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentRequest(
        template_id=template_id,
        version=version,
        target_environment=target_environment,
        parameter_values=parameter_values,
    )


class TestDeployTemplate:
    def test_deploy_template(self):
        deployment_service, template_version_service, _, binding_registry, activation_service = _build_context()
        template_version_service.publish("template-1", "v1")

        result = deployment_service.deploy(_request())

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentResult)
        assert result.successful is True
        assert len(result.instantiated_bindings) == 2
        assert deployment_service.deployment("template-1") == result

        for instance, source_id in zip(result.instantiated_bindings, ("binding-1", "binding-2")):
            assert instance.binding_id != source_id
            assert instance.profile_id == "development"
            assert binding_registry.find(instance.binding_id) == instance
            assert activation_service.state(instance.binding_id) == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE


class TestRedeployTemplate:
    def test_redeploy_template(self):
        deployment_service, template_version_service, template_registry, *_ = _build_context()
        template_version_service.publish("template-1", "v1")
        first = deployment_service.deploy(_request())

        template_registry.replace(_template("template-1", binding_ids=("binding-2",)))
        template_version_service.publish("template-1", "v2")

        redeployed = deployment_service.redeploy("template-1")

        assert redeployed.deployment_id == first.deployment_id
        assert len(redeployed.instantiated_bindings) == 1
        assert redeployed.instantiated_bindings[0].capability_id == "capability-binding-2"
        assert deployment_service.deployment("template-1") == redeployed

    def test_redeploy_without_active_deployment_raises(self):
        deployment_service, template_version_service, *_ = _build_context()
        template_version_service.publish("template-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError):
            deployment_service.redeploy("template-1")


class TestUndeployTemplate:
    def test_undeploy_template(self):
        deployment_service, template_version_service, *_ = _build_context()
        template_version_service.publish("template-1", "v1")
        deployment_service.deploy(_request())

        deployment_service.undeploy("template-1")

        assert deployment_service.deployment("template-1") is None

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError):
            deployment_service.undeploy("template-1")


class TestAtomicDeploymentFailure:
    def test_unknown_source_binding_fails_whole_deployment(self):
        deployment_service, template_version_service, *_ = _build_context(
            binding_ids=("binding-1",),
            template_binding_ids=("binding-1", "binding-missing"),
        )
        template_version_service.publish("template-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError):
            deployment_service.deploy(_request())

        assert deployment_service.deployment("template-1") is None


class TestDeploymentLookup:
    def test_deployment_lookup(self):
        deployment_service, template_version_service, *_ = _build_context()

        assert deployment_service.deployment("template-1") is None

        template_version_service.publish("template-1", "v1")
        result = deployment_service.deploy(_request())

        assert deployment_service.deployment("template-1") == result

    def test_reject_blank_template_id(self):
        deployment_service, *_ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError):
            deployment_service.deployment("   ")


class TestDuplicateDeploymentRejection:
    def test_duplicate_active_deployment_rejected(self):
        deployment_service, template_version_service, *_ = _build_context()
        template_version_service.publish("template-1", "v1")
        deployment_service.deploy(_request())

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError):
            deployment_service.deploy(_request())


class TestImmutableDeploymentResult:
    def test_immutable_result(self):
        deployment_service, template_version_service, *_ = _build_context()
        template_version_service.publish("template-1", "v1")

        result = deployment_service.deploy(_request())

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.successful = False


class TestRejectInvalidRequests:
    def test_reject_none_request(self):
        deployment_service, *_ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError):
            deployment_service.deploy(None)

    def test_reject_blank_request_fields(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError):
            _request(template_id="   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError):
            _request(version=None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError):
            _request(target_environment="   ")

    def test_reject_unknown_template_or_version(self):
        deployment_service, template_version_service, *_ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError):
            deployment_service.deploy(_request(template_id="template-missing"))

        template_version_service.publish("template-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError):
            deployment_service.deploy(_request(version="v-missing"))

    def test_reject_stale_unreleased_version(self):
        deployment_service, template_version_service, template_registry, *_ = _build_context()
        template_version_service.publish("template-1", "v1")

        template_registry.replace(_template("template-1", binding_ids=("binding-2",)))
        template_version_service.publish("template-1", "v2")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError):
            deployment_service.deploy(_request(version="v1"))

    def test_reject_none_dependencies(self):
        deployment_service, template_version_service, _, binding_registry, activation_service = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentService(
                None, binding_registry, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentService(
                template_version_service, None, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentService(
                template_version_service, binding_registry, None
            )
