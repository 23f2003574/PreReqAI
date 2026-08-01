import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRelease,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionService,
)


def _preset(preset_id, binding_template_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset(
        preset_id=preset_id,
        name=preset_id,
        description="A preset.",
        binding_template_ids=binding_template_ids,
    )


def _build_context(preset_id="preset-1"):
    preset_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()
    preset_registry.register(_preset(preset_id, binding_template_ids=("template-1",)))

    parameterization_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService(
        preset_registry,
        {},
    )

    preset_version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionService(
        preset_registry,
        parameterization_service,
    )

    release_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseService(
        preset_registry,
        preset_version_service,
    )

    return {
        "release_service": release_service,
        "preset_registry": preset_registry,
        "preset_version_service": preset_version_service,
        "preset_id": preset_id,
    }


def _publish(context, version):
    context["preset_version_service"].publish(context["preset_id"], version)


class TestReleaseVersion:
    def test_release_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        result = context["release_service"].release(context["preset_id"], "1.0.0")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseResult)
        assert result.previous_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus.DRAFT
        assert result.current_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus.RELEASED
        assert isinstance(result.release, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRelease)
        assert result.release.preset_id == context["preset_id"]
        assert result.release.version == "1.0.0"


class TestRetireVersion:
    def test_retire_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["release_service"].release(context["preset_id"], "1.0.0")
        result = context["release_service"].retire(context["preset_id"], "1.0.0")

        assert result.previous_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus.RELEASED
        assert result.current_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus.RETIRED
        assert context["release_service"].is_released(context["preset_id"], "1.0.0") is False


class TestLatestReleaseLookup:
    def test_latest_release_lookup(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["preset_registry"].replace(
            _preset(context["preset_id"], binding_template_ids=("template-1", "template-2"))
        )
        _publish(context, "2.0.0")

        assert context["release_service"].latest_release(context["preset_id"]) is None

        context["release_service"].release(context["preset_id"], "1.0.0")
        latest = context["release_service"].release(context["preset_id"], "2.0.0")

        assert context["release_service"].latest_release(context["preset_id"]) == latest.release

        context["release_service"].retire(context["preset_id"], "2.0.0")

        assert context["release_service"].latest_release(context["preset_id"]).version == "1.0.0"


class TestIsReleasedTrueFalse:
    def test_is_released_true_and_false(self):
        context = _build_context()
        _publish(context, "1.0.0")

        assert context["release_service"].is_released(context["preset_id"], "1.0.0") is False

        context["release_service"].release(context["preset_id"], "1.0.0")

        assert context["release_service"].is_released(context["preset_id"], "1.0.0") is True


class TestDuplicateReleaseRejection:
    def test_reject_duplicate_release(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["release_service"].release(context["preset_id"], "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError):
            context["release_service"].release(context["preset_id"], "1.0.0")


class TestInvalidTransitionRejection:
    def test_reject_retiring_non_released_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError):
            context["release_service"].retire(context["preset_id"], "1.0.0")

    def test_reject_re_releasing_retired_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["release_service"].release(context["preset_id"], "1.0.0")
        context["release_service"].retire(context["preset_id"], "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError):
            context["release_service"].release(context["preset_id"], "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError):
            context["release_service"].retire(context["preset_id"], "1.0.0")

    def test_reject_unknown_preset(self):
        context = _build_context()
        _publish(context, "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError):
            context["release_service"].release("preset-missing", "1.0.0")

    def test_reject_unknown_version(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError):
            context["release_service"].release(context["preset_id"], "does-not-exist")

    def test_reject_blank_ids(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError):
            context["release_service"].release("   ", "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError):
            context["release_service"].release(context["preset_id"], None)


class TestImmutableReleaseHistory:
    def test_immutable_release_history(self):
        context = _build_context()
        _publish(context, "1.0.0")

        released = context["release_service"].release(context["preset_id"], "1.0.0").release

        with pytest.raises(dataclasses.FrozenInstanceError):
            released.status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus.RETIRED

        retired_result = context["release_service"].retire(context["preset_id"], "1.0.0")

        assert released.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus.RELEASED
        assert retired_result.release.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus.RETIRED
        assert retired_result.release.release_id == released.release_id


class TestDeploymentAllowedOnlyForReleasedVersions:
    def test_deployment_gate_reflects_release_status(self):
        context = _build_context()
        _publish(context, "1.0.0")

        def deployable(preset_id, version):
            return context["release_service"].is_released(preset_id, version)

        assert deployable(context["preset_id"], "1.0.0") is False

        context["release_service"].release(context["preset_id"], "1.0.0")
        assert deployable(context["preset_id"], "1.0.0") is True

        context["release_service"].retire(context["preset_id"], "1.0.0")
        assert deployable(context["preset_id"], "1.0.0") is False


class TestRejectNoneDependencies:
    def test_reject_none_dependencies(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseService(
                None, context["preset_version_service"]
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseService(
                context["preset_registry"], None
            )
