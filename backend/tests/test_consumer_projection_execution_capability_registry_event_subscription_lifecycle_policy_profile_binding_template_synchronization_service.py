import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSynchronizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionService,
)


class FakeTargetGateway:
    def __init__(self, failing=()):
        self.failing = set(failing)
        self.calls = []

    def push(self, template_id, target):
        self.calls.append((template_id, target))

        return (template_id, target) not in self.failing


def _template(template_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
        template_id=template_id,
        name=template_id,
        binding_ids=binding_ids,
        metadata={},
    )


def _build_service(templates=(("template-1", ("binding-1",)),), failing=()):
    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

    for template_id, binding_ids in templates:
        template_registry.register(_template(template_id, binding_ids=binding_ids))

    parameterization_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationService(
        template_registry,
        {},
    )

    template_version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionService(
        template_registry,
        parameterization_service,
    )

    release_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseService(
        template_registry,
        template_version_service,
    )

    gateway = FakeTargetGateway(failing=failing)

    service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSynchronizationService(
        template_registry,
        template_version_service,
        release_service,
        gateway,
    )

    return service, template_registry, template_version_service, release_service, gateway


class TestSyncSingleTemplate:
    def test_sync_single_template(self):
        service, *_ = _build_service()

        result = service.sync_target("template-1", "registry")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncResult)
        assert result.synchronized is True
        assert result.synchronized_targets == ("registry",)
        assert len(service.pending()) == 1

        applied = service.sync_all()

        assert applied.synchronized is True
        assert applied.synchronized_targets == ("registry",)
        assert applied.failed_targets == ()
        assert service.is_synchronized("template-1") is True
        assert service.pending() == ()


class TestSyncAllTemplates:
    def test_sync_all_templates(self):
        service, *_ = _build_service(templates=(("template-1", ("binding-1",)), ("template-2", ("binding-2",))))

        service.sync_target("template-1", "registry")
        service.sync_target("template-2", "cache")

        result = service.sync_all()

        assert result.synchronized is True
        assert result.synchronized_targets == ("registry", "cache")
        assert service.is_synchronized("template-1") is True
        assert service.is_synchronized("template-2") is True
        assert service.pending() == ()


class TestSyncSpecificTarget:
    def test_sync_specific_target(self):
        service, *_ = _build_service()

        service.sync_target("template-1", "registry")
        service.sync_target("template-1", "cache")
        service.sync_all()

        assert service.is_synchronized("template-1") is True

        result = service.sync("template-1")

        assert result.synchronized is False
        assert result.synchronized_targets == ()


class TestRetryFailedSync:
    def test_retry_failed_synchronization(self):
        service, _, _, _, gateway = _build_service(failing=(("template-1", "cache"),))

        service.sync_target("template-1", "cache")
        first_apply = service.sync_all()

        assert first_apply.synchronized is False
        assert first_apply.failed_targets == ("cache",)
        assert service.is_synchronized("template-1") is False

        gateway.failing.discard(("template-1", "cache"))

        retried = service.sync("template-1")

        assert retried.synchronized_targets == ("cache",)

        second_apply = service.sync_all()

        assert second_apply.synchronized is True
        assert second_apply.synchronized_targets == ("cache",)
        assert second_apply.failed_targets == ()
        assert service.is_synchronized("template-1") is True


class TestPendingSyncLookup:
    def test_pending_synchronization(self):
        service, *_ = _build_service()

        service.sync_target("template-1", "registry")

        pending = service.pending()

        assert len(pending) == 1
        assert pending[0].template_id == "template-1"
        assert pending[0].target == "registry"


class TestIdempotentSynchronization:
    def test_idempotent_when_unchanged(self):
        service, *_ = _build_service()

        service.sync_target("template-1", "registry")
        service.sync_all()

        second = service.sync_target("template-1", "registry")

        assert second.synchronized is False
        assert second.synchronized_targets == ()
        assert service.pending() == ()

    def test_reject_duplicate_pending_synchronization(self):
        service, *_ = _build_service()

        service.sync_target("template-1", "registry")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError):
            service.sync_target("template-1", "registry")


class TestVersionAndReleaseAwareSync:
    def test_publishing_a_version_invalidates_prior_sync(self):
        service, template_registry, template_version_service, release_service, _ = _build_service()

        service.sync_target("template-1", "registry")
        service.sync_all()

        assert service.is_synchronized("template-1") is True

        template_version_service.publish("template-1", "1.0.0")
        release_service.release("template-1", "1.0.0")

        result = service.sync_target("template-1", "registry")

        assert result.synchronized is True
        assert result.synchronized_targets == ("registry",)


class TestInvalidRequestRejection:
    def test_reject_blank_ids(self):
        service, *_ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError):
            service.sync_target("   ", "registry")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError):
            service.sync_target("template-1", None)

    def test_reject_unknown_template(self):
        service, *_ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError):
            service.sync_target("template-missing", "registry")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError):
            service.sync("template-missing")

    def test_reject_invalid_operation(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncRequest(
                template_id="template-1",
                operation="invalid",
                target="registry",
            )

    def test_reject_none_dependencies(self):
        _, template_registry, template_version_service, release_service, gateway = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSynchronizationService(
                None, template_version_service, release_service, gateway
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSynchronizationService(
                template_registry, None, release_service, gateway
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSynchronizationService(
                template_registry, template_version_service, None, gateway
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSynchronizationService(
                template_registry, template_version_service, release_service, None
            )


class TestImmutableSyncResults:
    def test_immutable_result(self):
        service, *_ = _build_service()

        result = service.sync_target("template-1", "registry")

        with pytest.raises(AttributeError):
            result.synchronized = False
