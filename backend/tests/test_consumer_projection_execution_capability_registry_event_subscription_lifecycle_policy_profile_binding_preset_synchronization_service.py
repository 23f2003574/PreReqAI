import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSynchronizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionService,
)


class FakeTargetGateway:
    def __init__(self, failing=()):
        self.failing = set(failing)
        self.calls = []

    def push(self, preset_id, target):
        self.calls.append((preset_id, target))

        return (preset_id, target) not in self.failing


def _preset(preset_id, binding_template_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset(
        preset_id=preset_id,
        name=preset_id,
        description="A preset.",
        binding_template_ids=binding_template_ids,
    )


def _build_service(presets=(("preset-1", ("template-1",)),), failing=()):
    preset_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()

    for preset_id, binding_template_ids in presets:
        preset_registry.register(_preset(preset_id, binding_template_ids=binding_template_ids))

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

    gateway = FakeTargetGateway(failing=failing)

    service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSynchronizationService(
        preset_registry,
        preset_version_service,
        release_service,
        gateway,
    )

    return service, preset_registry, preset_version_service, release_service, gateway


class TestSyncSinglePreset:
    def test_sync_single_preset(self):
        service, *_ = _build_service()

        result = service.sync_target("preset-1", "registry")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncResult)
        assert result.synchronized is True
        assert result.synchronized_targets == ("registry",)
        assert len(service.pending()) == 1

        applied = service.sync_all()

        assert applied.synchronized is True
        assert applied.synchronized_targets == ("registry",)
        assert applied.failed_targets == ()
        assert service.is_synchronized("preset-1") is True
        assert service.pending() == ()


class TestSyncAllPresets:
    def test_sync_all_presets(self):
        service, *_ = _build_service(presets=(("preset-1", ("template-1",)), ("preset-2", ("template-2",))))

        service.sync_target("preset-1", "registry")
        service.sync_target("preset-2", "cache")

        result = service.sync_all()

        assert result.synchronized is True
        assert result.synchronized_targets == ("registry", "cache")
        assert service.is_synchronized("preset-1") is True
        assert service.is_synchronized("preset-2") is True
        assert service.pending() == ()


class TestSyncSpecificTarget:
    def test_sync_specific_target(self):
        service, *_ = _build_service()

        service.sync_target("preset-1", "registry")
        service.sync_target("preset-1", "cache")
        service.sync_all()

        assert service.is_synchronized("preset-1") is True

        result = service.sync("preset-1")

        assert result.synchronized is False
        assert result.synchronized_targets == ()


class TestRetryFailedSync:
    def test_retry_failed_synchronization(self):
        service, _, _, _, gateway = _build_service(failing=(("preset-1", "cache"),))

        service.sync_target("preset-1", "cache")
        first_apply = service.sync_all()

        assert first_apply.synchronized is False
        assert first_apply.failed_targets == ("cache",)
        assert service.is_synchronized("preset-1") is False

        gateway.failing.discard(("preset-1", "cache"))

        retried = service.sync("preset-1")

        assert retried.synchronized_targets == ("cache",)

        second_apply = service.sync_all()

        assert second_apply.synchronized is True
        assert second_apply.synchronized_targets == ("cache",)
        assert second_apply.failed_targets == ()
        assert service.is_synchronized("preset-1") is True


class TestPendingSyncLookup:
    def test_pending_synchronization(self):
        service, *_ = _build_service()

        service.sync_target("preset-1", "registry")

        pending = service.pending()

        assert len(pending) == 1
        assert pending[0].preset_id == "preset-1"
        assert pending[0].target == "registry"


class TestIdempotentSynchronization:
    def test_idempotent_when_unchanged(self):
        service, *_ = _build_service()

        service.sync_target("preset-1", "registry")
        service.sync_all()

        second = service.sync_target("preset-1", "registry")

        assert second.synchronized is False
        assert second.synchronized_targets == ()
        assert service.pending() == ()

    def test_reject_duplicate_pending_synchronization(self):
        service, *_ = _build_service()

        service.sync_target("preset-1", "registry")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError):
            service.sync_target("preset-1", "registry")


class TestVersionAndReleaseAwareSync:
    def test_publishing_a_version_invalidates_prior_sync(self):
        service, preset_registry, preset_version_service, release_service, _ = _build_service()

        service.sync_target("preset-1", "registry")
        service.sync_all()

        assert service.is_synchronized("preset-1") is True

        preset_version_service.publish("preset-1", "1.0.0")
        release_service.release("preset-1", "1.0.0")

        result = service.sync_target("preset-1", "registry")

        assert result.synchronized is True
        assert result.synchronized_targets == ("registry",)


class TestInvalidRequestRejection:
    def test_reject_blank_ids(self):
        service, *_ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError):
            service.sync_target("   ", "registry")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError):
            service.sync_target("preset-1", None)

    def test_reject_unknown_preset(self):
        service, *_ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError):
            service.sync_target("preset-missing", "registry")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError):
            service.sync("preset-missing")

    def test_reject_invalid_operation(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncRequest(
                preset_id="preset-1",
                operation="invalid",
                target="registry",
            )

    def test_reject_none_dependencies(self):
        _, preset_registry, preset_version_service, release_service, gateway = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSynchronizationService(
                None, preset_version_service, release_service, gateway
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSynchronizationService(
                preset_registry, None, release_service, gateway
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSynchronizationService(
                preset_registry, preset_version_service, None, gateway
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSynchronizationService(
                preset_registry, preset_version_service, release_service, None
            )


class TestImmutableSyncResults:
    def test_immutable_result(self):
        service, *_ = _build_service()

        result = service.sync_target("preset-1", "registry")

        with pytest.raises(AttributeError):
            result.synchronized = False
