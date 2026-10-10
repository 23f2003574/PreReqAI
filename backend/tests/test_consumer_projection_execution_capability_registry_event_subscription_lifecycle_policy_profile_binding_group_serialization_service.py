from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupExport,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupImportResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
)


def _binding(binding_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id="development",
        capability_id=f"capability-{binding_id}",
        created_at=datetime.now(timezone.utc),
    )


def _group(group_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
        group_id=group_id,
        group_name=group_id,
        binding_ids=binding_ids,
    )


def _build_service(binding_ids=("binding-1", "binding-2")):
    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

    for binding_id in binding_ids:
        binding_registry.register(_binding(binding_id))

    group_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

    serialization_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationService(
        group_registry,
        binding_registry,
    )

    return serialization_service, group_registry, binding_registry


class TestBindingGroupSerializationService:
    def test_export_all_groups(self):
        serialization_service, group_registry, _ = _build_service()

        group_registry.register(_group("group-b", binding_ids=("binding-2",)))
        group_registry.register(_group("group-a", binding_ids=("binding-1",)))

        export = serialization_service.export()

        assert isinstance(export, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupExport)
        assert [g.group_id for g in export.groups] == ["group-a", "group-b"]
        assert export.metadata["group_count"] == 2
        assert export.exported_at is not None

    def test_export_single_group(self):
        serialization_service, group_registry, _ = _build_service()

        group_registry.register(_group("group-a", binding_ids=("binding-1",)))
        group_registry.register(_group("group-b", binding_ids=("binding-2",)))

        export = serialization_service.export_group("group-a")

        assert len(export.groups) == 1
        assert export.groups[0].group_id == "group-a"
        assert export.groups[0].binding_ids == ("binding-1",)
        assert export.metadata["group_count"] == 1

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError):
            serialization_service.export_group("group-unknown")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError):
            serialization_service.export_group("   ")

    def test_import_groups(self):
        source_service, source_group_registry, _ = _build_service()
        source_group_registry.register(_group("group-a", binding_ids=("binding-1",)))

        export = source_service.export()

        target_service, target_group_registry, _ = _build_service()
        result = target_service.import_groups(export)

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupImportResult)
        assert result.imported == ("group-a",)
        assert result.skipped == ()
        assert result.failed == ()
        assert target_group_registry.find("group-a").binding_ids == ("binding-1",)

    def test_skip_duplicates(self):
        source_service, source_group_registry, _ = _build_service()
        source_group_registry.register(_group("group-a", binding_ids=("binding-1",)))

        export = source_service.export()

        target_service, _, _ = _build_service()

        first = target_service.import_groups(export)
        second = target_service.import_groups(export)

        assert first.imported == ("group-a",)
        assert second.imported == ()
        assert second.skipped == ("group-a",)
        assert second.failed == ()

    def test_validate_import(self):
        source_service, source_group_registry, _ = _build_service()
        source_group_registry.register(_group("group-a", binding_ids=("binding-1",)))

        export = source_service.export()

        target_service, _, _ = _build_service()

        assert target_service.validate_import(export) is True

    def test_malformed_import_rejection(self):
        serialization_service, _, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError):
            serialization_service.validate_import(None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError):
            serialization_service.validate_import("not-an-export")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError):
            serialization_service.import_groups(None)

    def test_reject_unknown_binding_and_duplicate_group_ids(self):
        source_service, source_group_registry, _ = _build_service()
        source_group_registry.register(_group("group-a", binding_ids=("binding-1",)))

        export = source_service.export()

        target_service, _, _ = _build_service(binding_ids=("binding-2",))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError):
            target_service.validate_import(export)

        duplicated_service, duplicated_group_registry, _ = _build_service()
        duplicated_group_registry.register(_group("group-a", binding_ids=("binding-1",)))
        single_export = duplicated_service.export_group("group-a")

        duplicate_export = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupExport(
            exported_at=single_export.exported_at,
            groups=single_export.groups + single_export.groups,
            metadata={"group_count": 2},
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError):
            duplicated_service.validate_import(duplicate_export)

    def test_reject_invalid_metadata(self):
        serialization_service, group_registry, _ = _build_service()
        group_registry.register(_group("group-a", binding_ids=("binding-1",)))

        export = serialization_service.export()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupExport(
                exported_at=export.exported_at,
                groups=export.groups,
                metadata=None,
            )

    def test_immutable_results(self):
        serialization_service, group_registry, _ = _build_service()
        group_registry.register(_group("group-a", binding_ids=("binding-1",)))

        export = serialization_service.export()

        with pytest.raises(AttributeError):
            export.exported_at = None

        result = serialization_service.import_groups(serialization_service.export())

        with pytest.raises(AttributeError):
            result.imported = ()

    def test_reject_none_dependencies(self):
        _, group_registry, binding_registry = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationService(None, binding_registry)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationService(group_registry, None)
