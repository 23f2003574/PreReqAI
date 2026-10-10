import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
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


def _preset(preset_id, binding_template_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset(
        preset_id=preset_id,
        name=preset_id,
        description="A preset.",
        binding_template_ids=binding_template_ids,
    )


def _build_context(
    binding_ids=("binding-1", "binding-2", "binding-3"),
    templates=(("template-1", ("binding-1", "binding-2")), ("template-2", ("binding-3",))),
    preset_template_ids=("template-1", "template-2"),
):
    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

    for binding_id in binding_ids:
        binding_registry.register(_binding(binding_id))

    activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(
        binding_registry,
        FakeClock(datetime.now(timezone.utc)),
    )

    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

    for template_id, template_binding_ids in templates:
        template_registry.register(_template(template_id, binding_ids=template_binding_ids))

    preset_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()
    preset_registry.register(_preset("preset-1", binding_template_ids=preset_template_ids))

    parameterization_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService(
        preset_registry,
        {},
    )

    preset_version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionService(
        preset_registry,
        parameterization_service,
    )

    deployment_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentService(
        preset_version_service,
        template_registry,
        binding_registry,
        activation_service,
    )

    return deployment_service, preset_version_service, preset_registry, template_registry, binding_registry, activation_service


def _request(preset_id="preset-1", version="v1", target_environment="production", parameter_values=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentRequest(
        preset_id=preset_id,
        version=version,
        target_environment=target_environment,
        parameter_values=parameter_values,
    )


class TestDeployPreset:
    def test_deploy_preset(self):
        deployment_service, preset_version_service, _, _, binding_registry, activation_service = _build_context()
        preset_version_service.publish("preset-1", "v1")

        result = deployment_service.deploy(_request())

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentResult)
        assert result.successful is True
        assert len(result.instantiated_binding_ids) == 3
        assert deployment_service.deployment("preset-1") == result

        for binding_id in result.instantiated_binding_ids:
            assert binding_registry.find(binding_id) is not None
            assert activation_service.state(binding_id) == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE


class TestRedeployPreset:
    def test_redeploy_preset(self):
        deployment_service, preset_version_service, preset_registry, *_ = _build_context()
        preset_version_service.publish("preset-1", "v1")
        first = deployment_service.deploy(_request())

        preset_registry.replace(_preset("preset-1", binding_template_ids=("template-1",)))
        preset_version_service.publish("preset-1", "v2")

        redeployed = deployment_service.redeploy("preset-1")

        assert redeployed.deployment_id == first.deployment_id
        assert len(redeployed.instantiated_binding_ids) == 2
        assert deployment_service.deployment("preset-1") == redeployed

    def test_redeploy_without_active_deployment_raises(self):
        deployment_service, preset_version_service, *_ = _build_context()
        preset_version_service.publish("preset-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            deployment_service.redeploy("preset-1")


class TestUndeployPreset:
    def test_undeploy_preset(self):
        deployment_service, preset_version_service, *_ = _build_context()
        preset_version_service.publish("preset-1", "v1")
        deployment_service.deploy(_request())

        deployment_service.undeploy("preset-1")

        assert deployment_service.deployment("preset-1") is None

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            deployment_service.undeploy("preset-1")


class TestAtomicDeploymentFailure:
    def test_unknown_template_fails_whole_deployment(self):
        deployment_service, preset_version_service, *_ = _build_context(
            preset_template_ids=("template-1", "template-missing"),
        )
        preset_version_service.publish("preset-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            deployment_service.deploy(_request())

        assert deployment_service.deployment("preset-1") is None

    def test_unknown_source_binding_fails_whole_deployment(self):
        deployment_service, preset_version_service, *_ = _build_context(
            binding_ids=("binding-1",),
            templates=(("template-1", ("binding-1", "binding-missing")),),
            preset_template_ids=("template-1",),
        )
        preset_version_service.publish("preset-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            deployment_service.deploy(_request())

        assert deployment_service.deployment("preset-1") is None


class TestDeploymentLookup:
    def test_deployment_lookup(self):
        deployment_service, preset_version_service, *_ = _build_context()

        assert deployment_service.deployment("preset-1") is None

        preset_version_service.publish("preset-1", "v1")
        result = deployment_service.deploy(_request())

        assert deployment_service.deployment("preset-1") == result

    def test_reject_blank_preset_id(self):
        deployment_service, *_ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            deployment_service.deployment("   ")


class TestDuplicateDeploymentRejection:
    def test_duplicate_active_deployment_rejected(self):
        deployment_service, preset_version_service, *_ = _build_context()
        preset_version_service.publish("preset-1", "v1")
        deployment_service.deploy(_request())

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            deployment_service.deploy(_request())


class TestImmutableDeploymentResult:
    def test_immutable_result(self):
        deployment_service, preset_version_service, *_ = _build_context()
        preset_version_service.publish("preset-1", "v1")

        result = deployment_service.deploy(_request())

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.successful = False


class TestRejectInvalidRequests:
    def test_reject_none_request(self):
        deployment_service, *_ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            deployment_service.deploy(None)

    def test_reject_blank_request_fields(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            _request(preset_id="   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            _request(version=None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            _request(target_environment="   ")

    def test_reject_unknown_preset_or_version(self):
        deployment_service, preset_version_service, *_ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            deployment_service.deploy(_request(preset_id="preset-missing"))

        preset_version_service.publish("preset-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            deployment_service.deploy(_request(version="v-missing"))

    def test_reject_stale_unreleased_version(self):
        deployment_service, preset_version_service, preset_registry, *_ = _build_context()
        preset_version_service.publish("preset-1", "v1")

        preset_registry.replace(_preset("preset-1", binding_template_ids=("template-1",)))
        preset_version_service.publish("preset-1", "v2")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            deployment_service.deploy(_request(version="v1"))

    def test_reject_none_dependencies(self):
        deployment_service, preset_version_service, _, template_registry, binding_registry, activation_service = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentService(
                None, template_registry, binding_registry, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentService(
                preset_version_service, None, binding_registry, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentService(
                preset_version_service, template_registry, None, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentService(
                preset_version_service, template_registry, binding_registry, None
            )
