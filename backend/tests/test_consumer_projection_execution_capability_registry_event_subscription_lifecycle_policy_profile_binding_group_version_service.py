import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionService,
)


def _group(group_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
        group_id=group_id,
        group_name=group_id,
        binding_ids=binding_ids,
    )


def _build_service(groups=(("group-1", ("binding-1", "binding-2")),)):
    group_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

    for group_id, binding_ids in groups:
        group_registry.register(_group(group_id, binding_ids=binding_ids))

    service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionService(
        group_registry
    )

    return service, group_registry


class TestPublishVersion:
    def test_publish_version(self):
        service, _ = _build_service()

        version = service.publish("group-1", "v1")

        assert isinstance(version, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersion)
        assert version.version == "v1"
        assert version.binding_ids == ("binding-1", "binding-2")
        assert version.created_at is not None

    def test_publish_multiple_versions(self):
        service, group_registry = _build_service()

        service.publish("group-1", "v1")

        group_registry.replace(_group("group-1", binding_ids=("binding-1",)))
        service.publish("group-1", "v2")

        history = service.history("group-1")

        assert [v.version for v in history.versions] == ["v1", "v2"]
        assert history.current_version == "v2"

    def test_reject_duplicate_version(self):
        service, _ = _build_service()

        service.publish("group-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError):
            service.publish("group-1", "v1")

    def test_reject_unknown_group(self):
        service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError):
            service.publish("group-missing", "v1")

    def test_reject_blank_identifiers(self):
        service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError):
            service.publish("   ", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError):
            service.publish("group-1", None)


class TestLatestLookup:
    def test_latest_lookup(self):
        service, group_registry = _build_service()

        service.publish("group-1", "v1")
        group_registry.replace(_group("group-1", binding_ids=("binding-2",)))
        second = service.publish("group-1", "v2")

        assert service.latest("group-1") == second

    def test_latest_unknown_group_raises(self):
        service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError):
            service.latest("group-missing")


class TestFindVersion:
    def test_find_existing_version(self):
        service, _ = _build_service()

        published = service.publish("group-1", "v1")

        assert service.find("group-1", "v1") == published

    def test_find_missing_version_returns_none(self):
        service, _ = _build_service()

        service.publish("group-1", "v1")

        assert service.find("group-1", "v-missing") is None

    def test_find_unknown_group_returns_none(self):
        service, _ = _build_service()

        assert service.find("group-missing", "v1") is None


class TestVersionHistory:
    def test_history(self):
        service, _ = _build_service()

        first = service.publish("group-1", "v1")
        second = service.publish("group-1", "v2")

        history = service.history("group-1")

        assert isinstance(history, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionHistory)
        assert history.group_id == "group-1"
        assert history.current_version == "v2"
        assert history.versions == (first, second)

    def test_history_unknown_group_raises(self):
        service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError):
            service.history("group-missing")


class TestRollback:
    def test_rollback_creates_new_current_version(self):
        service, group_registry = _build_service()

        first = service.publish("group-1", "v1")
        group_registry.replace(_group("group-1", binding_ids=("binding-2",)))
        service.publish("group-1", "v2")

        restored = service.rollback("group-1", "v1")

        assert restored.version != "v1"
        assert restored.version != "v2"
        assert restored.binding_ids == first.binding_ids

        history = service.history("group-1")

        assert history.current_version == restored.version
        assert [v.version for v in history.versions] == ["v1", "v2", restored.version]

    def test_rollback_unknown_version_raises(self):
        service, _ = _build_service()

        service.publish("group-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError):
            service.rollback("group-1", "v-missing")

    def test_rollback_unknown_group_raises(self):
        service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError):
            service.rollback("group-missing", "v1")

    def test_reject_blank_identifiers(self):
        service, _ = _build_service()

        service.publish("group-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError):
            service.rollback("group-1", "   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError):
            service.rollback(None, "v1")


class TestImmutableHistory:
    def test_immutable_history(self):
        service, _ = _build_service()

        service.publish("group-1", "v1")

        history = service.history("group-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            history.current_version = "v-changed"

    def test_immutable_version(self):
        service, _ = _build_service()

        version = service.publish("group-1", "v1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            version.version = "v-changed"

    def test_does_not_mutate_prior_versions_on_rollback(self):
        service, group_registry = _build_service()

        first = service.publish("group-1", "v1")
        group_registry.replace(_group("group-1", binding_ids=("binding-2",)))
        service.publish("group-1", "v2")

        service.rollback("group-1", "v1")

        assert service.find("group-1", "v1") == first
