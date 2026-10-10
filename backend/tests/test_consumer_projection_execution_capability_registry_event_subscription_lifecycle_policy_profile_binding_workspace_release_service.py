import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRelease,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionService,
)


def _workspace(workspace_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace(
        workspace_id=workspace_id,
        name=workspace_id,
        description="A workspace.",
        binding_ids=(),
        template_ids=(),
        preset_ids=(),
        group_ids=(),
    )


def _build_context(workspace_id="workspace-1"):
    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()
    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()
    preset_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()
    group_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

    workspace_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()
    workspace_registry.register(_workspace(workspace_id))

    workspace_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService(
        binding_registry, template_registry, preset_registry, group_registry
    )
    workspace_service.create(_workspace(workspace_id))

    workspace_version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionService(
        workspace_service
    )

    release_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseService(
        workspace_registry,
        workspace_version_service,
    )

    return {
        "release_service": release_service,
        "workspace_registry": workspace_registry,
        "workspace_version_service": workspace_version_service,
        "workspace_id": workspace_id,
    }


def _publish(context, version):
    context["workspace_version_service"].publish(context["workspace_id"], version)


class TestReleaseVersion:
    def test_release_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        result = context["release_service"].release(context["workspace_id"], "1.0.0")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseResult)
        assert result.previous_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus.DRAFT
        assert result.current_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus.RELEASED
        assert isinstance(result.release, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRelease)
        assert result.release.workspace_id == context["workspace_id"]
        assert result.release.version == "1.0.0"


class TestRetireVersion:
    def test_retire_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["release_service"].release(context["workspace_id"], "1.0.0")
        result = context["release_service"].retire(context["workspace_id"], "1.0.0")

        assert result.previous_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus.RELEASED
        assert result.current_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus.RETIRED
        assert context["release_service"].is_released(context["workspace_id"], "1.0.0") is False


class TestLatestReleaseLookup:
    def test_latest_release_lookup(self):
        context = _build_context()
        _publish(context, "1.0.0")
        _publish(context, "2.0.0")

        assert context["release_service"].latest_release(context["workspace_id"]) is None

        context["release_service"].release(context["workspace_id"], "1.0.0")
        latest = context["release_service"].release(context["workspace_id"], "2.0.0")

        assert context["release_service"].latest_release(context["workspace_id"]) == latest.release

        context["release_service"].retire(context["workspace_id"], "2.0.0")

        assert context["release_service"].latest_release(context["workspace_id"]).version == "1.0.0"


class TestIsReleasedTrueFalse:
    def test_is_released_true_and_false(self):
        context = _build_context()
        _publish(context, "1.0.0")

        assert context["release_service"].is_released(context["workspace_id"], "1.0.0") is False

        context["release_service"].release(context["workspace_id"], "1.0.0")

        assert context["release_service"].is_released(context["workspace_id"], "1.0.0") is True


class TestDuplicateReleaseRejection:
    def test_reject_duplicate_release(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["release_service"].release(context["workspace_id"], "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError):
            context["release_service"].release(context["workspace_id"], "1.0.0")


class TestInvalidTransitionRejection:
    def test_reject_retiring_non_released_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError):
            context["release_service"].retire(context["workspace_id"], "1.0.0")

    def test_reject_re_releasing_retired_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["release_service"].release(context["workspace_id"], "1.0.0")
        context["release_service"].retire(context["workspace_id"], "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError):
            context["release_service"].release(context["workspace_id"], "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError):
            context["release_service"].retire(context["workspace_id"], "1.0.0")

    def test_reject_unknown_workspace(self):
        context = _build_context()
        _publish(context, "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError):
            context["release_service"].release("workspace-missing", "1.0.0")

    def test_reject_unknown_version(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError):
            context["release_service"].release(context["workspace_id"], "does-not-exist")

    def test_reject_blank_ids(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError):
            context["release_service"].release("   ", "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError):
            context["release_service"].release(context["workspace_id"], None)


class TestImmutableReleaseHistory:
    def test_immutable_release_history(self):
        context = _build_context()
        _publish(context, "1.0.0")

        released = context["release_service"].release(context["workspace_id"], "1.0.0").release

        with pytest.raises(dataclasses.FrozenInstanceError):
            released.status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus.RETIRED

        retired_result = context["release_service"].retire(context["workspace_id"], "1.0.0")

        assert released.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus.RELEASED
        assert retired_result.release.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus.RETIRED
        assert retired_result.release.release_id == released.release_id


class TestDeploymentAllowedOnlyForReleasedVersions:
    def test_deployment_gate_reflects_release_status(self):
        context = _build_context()
        _publish(context, "1.0.0")

        def deployable(workspace_id, version):
            return context["release_service"].is_released(workspace_id, version)

        assert deployable(context["workspace_id"], "1.0.0") is False

        context["release_service"].release(context["workspace_id"], "1.0.0")
        assert deployable(context["workspace_id"], "1.0.0") is True

        context["release_service"].retire(context["workspace_id"], "1.0.0")
        assert deployable(context["workspace_id"], "1.0.0") is False


class TestRejectNoneDependencies:
    def test_reject_none_dependencies(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseService(
                None, context["workspace_version_service"]
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseService(
                context["workspace_registry"], None
            )
