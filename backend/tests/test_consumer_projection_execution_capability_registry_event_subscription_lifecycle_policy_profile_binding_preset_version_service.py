import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameter,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionService,
)


def _preset(preset_id, binding_template_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset(
        preset_id=preset_id,
        name=preset_id,
        description="A preset.",
        binding_template_ids=binding_template_ids,
    )


def _parameter(name, type_=str, required=False, default_value=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameter(
        name=name,
        type=type_,
        required=required,
        default_value=default_value,
    )


def _build_service(presets=(("preset-1", ("template-1", "template-2")),), parameter_definitions=None):
    preset_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()

    for preset_id, binding_template_ids in presets:
        preset_registry.register(_preset(preset_id, binding_template_ids=binding_template_ids))

    parameterization_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService(
        preset_registry,
        parameter_definitions or {},
    )

    service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionService(
        preset_registry,
        parameterization_service,
    )

    return service, preset_registry, parameterization_service


class TestPublishVersion:
    def test_publish_version(self):
        parameters = (_parameter("retry_limit", type_=int, default_value=3),)
        service, _, _ = _build_service(parameter_definitions={"preset-1": parameters})

        version = service.publish("preset-1", "v1")

        assert isinstance(version, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersion)
        assert version.version == "v1"
        assert version.template_ids == ("template-1", "template-2")
        assert version.parameters == parameters
        assert version.created_at is not None

    def test_publish_multiple_versions(self):
        service, preset_registry, _ = _build_service()

        service.publish("preset-1", "v1")

        preset_registry.replace(_preset("preset-1", binding_template_ids=("template-1",)))
        service.publish("preset-1", "v2")

        history = service.history("preset-1")

        assert [v.version for v in history.versions] == ["v1", "v2"]
        assert history.current_version == "v2"

    def test_reject_duplicate_version(self):
        service, _, _ = _build_service()

        service.publish("preset-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError):
            service.publish("preset-1", "v1")

    def test_reject_unknown_preset(self):
        service, _, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError):
            service.publish("preset-missing", "v1")

    def test_reject_blank_identifiers(self):
        service, _, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError):
            service.publish("   ", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError):
            service.publish("preset-1", None)


class TestLatestLookup:
    def test_latest_lookup(self):
        service, preset_registry, _ = _build_service()

        service.publish("preset-1", "v1")
        preset_registry.replace(_preset("preset-1", binding_template_ids=("template-2",)))
        second = service.publish("preset-1", "v2")

        assert service.latest("preset-1") == second

    def test_latest_unknown_preset_raises(self):
        service, _, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError):
            service.latest("preset-missing")


class TestFindVersion:
    def test_find_existing_version(self):
        service, _, _ = _build_service()

        published = service.publish("preset-1", "v1")

        assert service.find("preset-1", "v1") == published

    def test_find_missing_version_returns_none(self):
        service, _, _ = _build_service()

        service.publish("preset-1", "v1")

        assert service.find("preset-1", "v-missing") is None

    def test_find_unknown_preset_returns_none(self):
        service, _, _ = _build_service()

        assert service.find("preset-missing", "v1") is None


class TestVersionHistory:
    def test_history(self):
        service, _, _ = _build_service()

        first = service.publish("preset-1", "v1")
        second = service.publish("preset-1", "v2")

        history = service.history("preset-1")

        assert isinstance(history, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionHistory)
        assert history.preset_id == "preset-1"
        assert history.current_version == "v2"
        assert history.versions == (first, second)

    def test_history_unknown_preset_raises(self):
        service, _, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError):
            service.history("preset-missing")


class TestRollback:
    def test_rollback_creates_new_current_version(self):
        parameters = (_parameter("retry_limit", type_=int, default_value=3),)
        service, preset_registry, _ = _build_service(parameter_definitions={"preset-1": parameters})

        first = service.publish("preset-1", "v1")
        preset_registry.replace(_preset("preset-1", binding_template_ids=("template-2",)))
        service.publish("preset-1", "v2")

        restored = service.rollback("preset-1", "v1")

        assert restored.version != "v1"
        assert restored.version != "v2"
        assert restored.template_ids == first.template_ids
        assert restored.parameters == first.parameters

        history = service.history("preset-1")

        assert history.current_version == restored.version
        assert [v.version for v in history.versions] == ["v1", "v2", restored.version]

    def test_rollback_unknown_version_raises(self):
        service, _, _ = _build_service()

        service.publish("preset-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError):
            service.rollback("preset-1", "v-missing")

    def test_rollback_unknown_preset_raises(self):
        service, _, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError):
            service.rollback("preset-missing", "v1")

    def test_reject_blank_identifiers(self):
        service, _, _ = _build_service()

        service.publish("preset-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError):
            service.rollback("preset-1", "   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError):
            service.rollback(None, "v1")


class TestImmutableHistory:
    def test_immutable_history(self):
        service, _, _ = _build_service()

        service.publish("preset-1", "v1")

        history = service.history("preset-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            history.current_version = "v-changed"

    def test_immutable_version(self):
        service, _, _ = _build_service()

        version = service.publish("preset-1", "v1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            version.version = "v-changed"

    def test_does_not_mutate_prior_versions_on_rollback(self):
        service, preset_registry, _ = _build_service()

        first = service.publish("preset-1", "v1")
        preset_registry.replace(_preset("preset-1", binding_template_ids=("template-2",)))
        service.publish("preset-1", "v2")

        service.rollback("preset-1", "v1")

        assert service.find("preset-1", "v1") == first


class TestRejectNoneDependencies:
    def test_reject_none_dependencies(self):
        _, preset_registry, parameterization_service = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionService(
                None, parameterization_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionService(
                preset_registry, None
            )
