import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentExport,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentImportResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService,
)


def _build_profile(profile_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,
        profile_name=profile_id,
        description=f"Profile {profile_id}.",
        policy_identifiers=(f"policy-{profile_id}",),
    )


def _build_service(profile_ids=("development", "staging")):
    profile_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()

    for profile_id in profile_ids:
        profile_service.register(_build_profile(profile_id))

    assignment_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentService(profile_service)

    serialization_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationService(
        assignment_service,
        profile_service,
    )

    return serialization_service, assignment_service, profile_service


class TestProfileAssignmentSerializationService:
    def test_export_all_assignments(self):
        serialization_service, assignment_service, _ = _build_service()

        assignment_service.assign("target-b", "staging")
        assignment_service.assign("target-a", "development")

        export = serialization_service.export()

        assert isinstance(export, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentExport)
        assert [a.target_id for a in export.assignments] == ["target-a", "target-b"]
        assert export.metadata["target_count"] == 2
        assert export.exported_at is not None

    def test_export_single_target(self):
        serialization_service, assignment_service, _ = _build_service()

        assignment_service.assign("target-a", "development")
        assignment_service.assign("target-b", "staging")

        export = serialization_service.export_target("target-a")

        assert len(export.assignments) == 1
        assert export.assignments[0].target_id == "target-a"
        assert export.assignments[0].profile_id == "development"
        assert export.metadata["target_count"] == 1

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError):
            serialization_service.export_target("target-unknown")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError):
            serialization_service.export_target("   ")

    def test_import_assignments(self):
        source_service, source_assignment_service, _ = _build_service()
        source_assignment_service.assign("target-a", "development")

        export = source_service.export()

        target_service, target_assignment_service, _ = _build_service()
        result = target_service.import_assignments(export)

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentImportResult)
        assert result.imported == ("target-a",)
        assert result.skipped == ()
        assert result.failed == ()
        assert target_assignment_service.find("target-a").profile_id == "development"

    def test_skip_duplicates(self):
        source_service, source_assignment_service, _ = _build_service()
        source_assignment_service.assign("target-a", "development")

        export = source_service.export()

        target_service, _, _ = _build_service()

        first = target_service.import_assignments(export)
        second = target_service.import_assignments(export)

        assert first.imported == ("target-a",)
        assert second.imported == ()
        assert second.skipped == ("target-a",)
        assert second.failed == ()

    def test_validate_import(self):
        source_service, source_assignment_service, _ = _build_service()
        source_assignment_service.assign("target-a", "development")

        export = source_service.export()

        target_service, _, _ = _build_service()

        assert target_service.validate_import(export) is True

    def test_malformed_import_rejection(self):
        serialization_service, _, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError):
            serialization_service.validate_import(None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError):
            serialization_service.validate_import("not-an-export")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError):
            serialization_service.import_assignments(None)

    def test_reject_unknown_profile_and_duplicate_assignments(self):
        source_service, source_assignment_service, source_profile_service = _build_service()
        source_assignment_service.assign("target-a", "development")

        export = source_service.export()

        target_service, _, target_profile_service = _build_service(profile_ids=("staging",))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError):
            target_service.validate_import(export)

        duplicated_service, duplicated_assignment_service, _ = _build_service()
        duplicated_assignment_service.assign("target-a", "development")
        single_export = duplicated_service.export_target("target-a")

        duplicate_export = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentExport(
            exported_at=single_export.exported_at,
            assignments=single_export.assignments + single_export.assignments,
            metadata={"target_count": 2},
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError):
            duplicated_service.validate_import(duplicate_export)

    def test_reject_invalid_metadata(self):
        serialization_service, assignment_service, _ = _build_service()
        assignment_service.assign("target-a", "development")

        export = serialization_service.export()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentExport(
                exported_at=export.exported_at,
                assignments=export.assignments,
                metadata=None,
            )

    def test_immutable_results(self):
        serialization_service, assignment_service, _ = _build_service()
        assignment_service.assign("target-a", "development")

        export = serialization_service.export()

        with pytest.raises(AttributeError):
            export.exported_at = None

        result = serialization_service.import_assignments(
            serialization_service.export()
        )

        with pytest.raises(AttributeError):
            result.imported = ()
