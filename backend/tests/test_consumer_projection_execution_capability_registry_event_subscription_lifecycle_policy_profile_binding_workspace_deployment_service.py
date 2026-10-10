import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionService,
)


def _binding(binding_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id="development",
        capability_id=f"capability-{binding_id}",
        created_at=datetime.now(timezone.utc),
    )


def _workspace(workspace_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace(
        workspace_id=workspace_id,
        name=workspace_id,
        description="A workspace.",
        binding_ids=binding_ids,
        template_ids=(),
        preset_ids=(),
        group_ids=(),
    )


def _build_context(binding_ids=("binding-1", "binding-2")):
    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()
    for binding_id in binding_ids:
        binding_registry.register(_binding(binding_id))

    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()
    preset_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()
    group_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

    workspace_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()

    workspace_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService(
        binding_registry, template_registry, preset_registry, group_registry
    )

    workspace_version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionService(
        workspace_service
    )

    deployment_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentService(
        workspace_version_service,
        workspace_registry,
        binding_registry,
        template_registry,
        preset_registry,
        group_registry,
    )

    return {
        "deployment_service": deployment_service,
        "workspace_service": workspace_service,
        "workspace_version_service": workspace_version_service,
        "workspace_registry": workspace_registry,
        "binding_registry": binding_registry,
        "template_registry": template_registry,
        "preset_registry": preset_registry,
        "group_registry": group_registry,
    }


def _register_and_publish(context, workspace_id="workspace-1", binding_ids=(), version="v1"):
    workspace = _workspace(workspace_id, binding_ids=binding_ids)
    context["workspace_service"].create(workspace)
    context["workspace_registry"].register(workspace)
    context["workspace_version_service"].publish(workspace_id, version)


def _request(workspace_id="workspace-1", version="v1", target_environment="production"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentRequest(
        workspace_id=workspace_id,
        version=version,
        target_environment=target_environment,
    )


class TestDeployWorkspace:
    def test_deploy_workspace(self):
        context = _build_context()
        _register_and_publish(context, binding_ids=("binding-1", "binding-2"))

        result = context["deployment_service"].deploy(_request())

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentResult)
        assert result.successful is True
        assert result.deployed_resources["bindings"] == ("binding-1", "binding-2")
        assert context["deployment_service"].deployment("workspace-1") == result


class TestRedeployWorkspace:
    def test_redeploy_workspace(self):
        context = _build_context()
        _register_and_publish(context, binding_ids=("binding-1",))
        first = context["deployment_service"].deploy(_request())

        updated = _workspace("workspace-1", binding_ids=("binding-1", "binding-2"))
        context["workspace_service"].update(updated)
        context["workspace_registry"].replace(updated)
        context["workspace_version_service"].publish("workspace-1", "v2")

        redeployed = context["deployment_service"].redeploy("workspace-1")

        assert redeployed.deployment_id == first.deployment_id
        assert redeployed.deployed_resources["bindings"] == ("binding-1", "binding-2")
        assert context["deployment_service"].deployment("workspace-1") == redeployed

    def test_redeploy_without_active_deployment_raises(self):
        context = _build_context()
        _register_and_publish(context)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError):
            context["deployment_service"].redeploy("workspace-1")


class TestUndeployWorkspace:
    def test_undeploy_workspace(self):
        context = _build_context()
        _register_and_publish(context, binding_ids=("binding-1",))
        context["deployment_service"].deploy(_request())

        context["deployment_service"].undeploy("workspace-1")

        assert context["deployment_service"].deployment("workspace-1") is None

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError):
            context["deployment_service"].undeploy("workspace-1")


class TestAtomicDeploymentFailure:
    def test_unknown_binding_fails_whole_deployment(self):
        context = _build_context(binding_ids=("binding-1",))
        workspace = _workspace("workspace-1", binding_ids=("binding-1", "binding-missing"))
        context["workspace_service"].create(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace(
                workspace_id="workspace-1",
                name="workspace-1",
                description="A workspace.",
                binding_ids=("binding-1",),
                template_ids=(),
                preset_ids=(),
                group_ids=(),
            )
        )
        context["workspace_registry"].register(workspace)
        context["workspace_version_service"].publish("workspace-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError):
            context["deployment_service"].deploy(_request())

        assert context["deployment_service"].deployment("workspace-1") is None


class TestDeploymentLookup:
    def test_deployment_lookup(self):
        context = _build_context()

        assert context["deployment_service"].deployment("workspace-1") is None

        _register_and_publish(context, binding_ids=("binding-1",))
        result = context["deployment_service"].deploy(_request())

        assert context["deployment_service"].deployment("workspace-1") == result

    def test_reject_blank_workspace_id(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError):
            context["deployment_service"].deployment("   ")


class TestDuplicateDeploymentRejection:
    def test_duplicate_active_deployment_rejected(self):
        context = _build_context()
        _register_and_publish(context, binding_ids=("binding-1",))
        context["deployment_service"].deploy(_request())

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError):
            context["deployment_service"].deploy(_request())


class TestImmutableDeploymentResult:
    def test_immutable_result(self):
        context = _build_context()
        _register_and_publish(context, binding_ids=("binding-1",))

        result = context["deployment_service"].deploy(_request())

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.successful = False


class TestRejectInvalidRequests:
    def test_reject_none_request(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError):
            context["deployment_service"].deploy(None)

    def test_reject_blank_request_fields(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError):
            _request(workspace_id="   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError):
            _request(version=None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError):
            _request(target_environment="   ")

    def test_reject_unknown_workspace_or_version(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError):
            context["deployment_service"].deploy(_request(workspace_id="workspace-missing"))

        _register_and_publish(context, binding_ids=("binding-1",))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError):
            context["deployment_service"].deploy(_request(version="v-missing"))

    def test_reject_stale_unreleased_version(self):
        context = _build_context()
        _register_and_publish(context, binding_ids=("binding-1",))

        updated = _workspace("workspace-1", binding_ids=("binding-1", "binding-2"))
        context["workspace_service"].update(updated)
        context["workspace_registry"].replace(updated)
        context["workspace_version_service"].publish("workspace-1", "v2")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError):
            context["deployment_service"].deploy(_request(version="v1"))

    def test_reject_none_dependencies(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentService(
                None,
                context["workspace_registry"],
                context["binding_registry"],
                context["template_registry"],
                context["preset_registry"],
                context["group_registry"],
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentService(
                context["workspace_version_service"],
                None,
                context["binding_registry"],
                context["template_registry"],
                context["preset_registry"],
                context["group_registry"],
            )
