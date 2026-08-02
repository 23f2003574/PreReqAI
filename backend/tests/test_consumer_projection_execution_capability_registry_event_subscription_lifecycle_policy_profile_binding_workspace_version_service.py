import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionService,
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


def _build_service(workspaces=(("workspace-1", ()),)):
    binding_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()
    template_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()
    preset_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()
    group_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

    workspace_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService(
        binding_service, template_service, preset_service, group_service
    )

    for workspace_id, binding_ids in workspaces:
        workspace_service.create(_workspace(workspace_id, binding_ids=binding_ids))

    version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionService(
        workspace_service
    )

    return version_service, workspace_service


class TestPublishVersion:
    def test_publish_version(self):
        service, _ = _build_service()

        version = service.publish("workspace-1", "v1")

        assert isinstance(version, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersion)
        assert version.version == "v1"
        assert version.snapshot_id
        assert version.created_at is not None

    def test_publish_multiple_versions(self):
        service, _ = _build_service()

        service.publish("workspace-1", "v1")
        service.publish("workspace-1", "v2")

        history = service.history("workspace-1")

        assert [v.version for v in history.versions] == ["v1", "v2"]
        assert history.current_version == "v2"

    def test_reject_duplicate_version(self):
        service, _ = _build_service()

        service.publish("workspace-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError):
            service.publish("workspace-1", "v1")

    def test_reject_unknown_workspace(self):
        service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError):
            service.publish("workspace-missing", "v1")

    def test_reject_blank_identifiers(self):
        service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError):
            service.publish("   ", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError):
            service.publish("workspace-1", None)


class TestLatestLookup:
    def test_latest_lookup(self):
        service, _ = _build_service()

        service.publish("workspace-1", "v1")
        second = service.publish("workspace-1", "v2")

        assert service.latest("workspace-1") == second

    def test_latest_unknown_workspace_raises(self):
        service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError):
            service.latest("workspace-missing")


class TestFindVersion:
    def test_find_existing_version(self):
        service, _ = _build_service()

        published = service.publish("workspace-1", "v1")

        assert service.find("workspace-1", "v1") == published

    def test_find_missing_version_returns_none(self):
        service, _ = _build_service()

        service.publish("workspace-1", "v1")

        assert service.find("workspace-1", "v-missing") is None

    def test_find_unknown_workspace_returns_none(self):
        service, _ = _build_service()

        assert service.find("workspace-missing", "v1") is None


class TestVersionHistory:
    def test_history(self):
        service, _ = _build_service()

        first = service.publish("workspace-1", "v1")
        second = service.publish("workspace-1", "v2")

        history = service.history("workspace-1")

        assert isinstance(history, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionHistory)
        assert history.workspace_id == "workspace-1"
        assert history.current_version == "v2"
        assert history.versions == (first, second)

    def test_history_unknown_workspace_raises(self):
        service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError):
            service.history("workspace-missing")


class TestRollback:
    def test_rollback_creates_new_current_version(self):
        service, _ = _build_service()

        first = service.publish("workspace-1", "v1")
        service.publish("workspace-1", "v2")

        restored = service.rollback("workspace-1", "v1")

        assert restored.version != "v1"
        assert restored.version != "v2"
        assert restored.snapshot_id == first.snapshot_id

        history = service.history("workspace-1")

        assert history.current_version == restored.version
        assert [v.version for v in history.versions] == ["v1", "v2", restored.version]

    def test_rollback_unknown_version_raises(self):
        service, _ = _build_service()

        service.publish("workspace-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError):
            service.rollback("workspace-1", "v-missing")

    def test_rollback_unknown_workspace_raises(self):
        service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError):
            service.rollback("workspace-missing", "v1")

    def test_reject_blank_identifiers(self):
        service, _ = _build_service()

        service.publish("workspace-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError):
            service.rollback("workspace-1", "   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError):
            service.rollback(None, "v1")


class TestImmutableHistory:
    def test_immutable_history(self):
        service, _ = _build_service()

        service.publish("workspace-1", "v1")

        history = service.history("workspace-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            history.current_version = "v-changed"

    def test_immutable_version(self):
        service, _ = _build_service()

        version = service.publish("workspace-1", "v1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            version.version = "v-changed"

    def test_does_not_mutate_prior_versions_on_rollback(self):
        service, _ = _build_service()

        first = service.publish("workspace-1", "v1")
        service.publish("workspace-1", "v2")

        service.rollback("workspace-1", "v1")

        assert service.find("workspace-1", "v1") == first


class TestRejectNoneDependencies:
    def test_reject_none_dependencies(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionService(None)
