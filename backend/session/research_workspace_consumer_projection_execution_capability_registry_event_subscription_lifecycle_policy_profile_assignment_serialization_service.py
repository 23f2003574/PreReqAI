from datetime import (
    datetime,
    timezone,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_export import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentExport,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_import_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentImportResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_serialization_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationService:
    """
    Exports and imports consumer projection execution capability
    registry event subscription lifecycle policy profile assignments,
    enabling persistence and transfer of assignment configurations
    between registries, environments, and deployments.

    The service's responsibility is capturing and reconstructing
    assignment configurations, not assigning profiles, registering
    profiles, persisting exports externally, logging, or publishing
    events.

    The service is:
    - Deterministic: export() always orders assignments by target ID,
      so the same assignment state always produces the same export
    - Metadata-preserving: Exported assignment records are carried
      through unchanged, never reconstructed or reformatted
    - Idempotent: Importing the same export more than once leaves
      already-synchronized targets untouched
    """

    def __init__(
        self,
        assignment_service,
        profile_service,
    ):
        """
        Args:
            assignment_service: The assignment service used to read
                and apply assignments. Any object exposing
                `find(target_id)`, `is_assigned(target_id)`, `list()`,
                and `assign(target_id, profile_id)` is accepted
            profile_service: The profile service used to verify a
                profile exists. Any object exposing
                `contains(profile_id)` is accepted
        """

        if assignment_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError(
                "Cannot initialize serialization service with a None assignment service."
            )

        if profile_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError(
                "Cannot initialize serialization service with a None profile service."
            )

        self._assignment_service = assignment_service
        self._profile_service = profile_service

    def export(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentExport:
        """
        Export every currently active assignment.

        Returns:
            An immutable export carrying every active assignment,
            ordered deterministically by target ID
        """

        target_ids = sorted(
            {record.target_id for record in self._assignment_service.list()}
        )

        assignments = tuple(
            active
            for active in (
                self._assignment_service.find(target_id) for target_id in target_ids
            )
            if active is not None
        )

        return self._build_export(assignments)

    def export_target(
        self,
        target_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentExport:
        """
        Export the currently active assignment for a single target.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError:
                If target_id is None/blank, or no assignment is
                actively assigned to it
        """

        if target_id is None or not target_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError(
                "Cannot export with an empty or blank target ID."
            )

        active = self._assignment_service.find(target_id)

        if active is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError(
                f"Cannot export target ID {target_id!r}: no active assignment found."
            )

        return self._build_export((active,))

    def validate_import(
        self,
        export_data,
    ) -> bool:
        """
        Validate an export before importing it.

        Returns:
            True if the export is well-formed and every referenced
            profile is known

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError:
                If export_data is None, is not a well-formed export,
                contains duplicate assignments for the same target,
                references an unknown profile, or carries invalid
                metadata
        """

        if export_data is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError(
                "Cannot validate a None export."
            )

        if not isinstance(
            export_data,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentExport,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError(
                "Cannot validate malformed export data: expected a profile assignment export."
            )

        if not isinstance(export_data.metadata, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError(
                "Cannot validate an export with invalid metadata."
            )

        seen_target_ids = set()

        for assignment in export_data.assignments:
            target_id = getattr(assignment, "target_id", None)
            profile_id = getattr(assignment, "profile_id", None)

            if target_id is None or not target_id.strip() or profile_id is None or not profile_id.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError(
                    "Cannot validate malformed export data: every assignment requires a target ID and a profile ID."
                )

            if target_id in seen_target_ids:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError(
                    f"Cannot validate an export with a duplicate assignment for target ID {target_id!r}."
                )

            seen_target_ids.add(target_id)

            if not self._profile_service.contains(profile_id):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError(
                    f"Cannot validate an export referencing unknown profile ID {profile_id!r}."
                )

        return True

    def import_assignments(
        self,
        export_data,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentImportResult:
        """
        Import assignments from an export, applying only the
        assignments that changed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSerializationError:
                If export_data fails validate_import()
        """

        self.validate_import(export_data)

        imported = []
        skipped = []
        failed = []

        for assignment in export_data.assignments:
            current = self._assignment_service.find(assignment.target_id)

            if current is not None and current.profile_id == assignment.profile_id:
                skipped.append(assignment.target_id)
                continue

            try:
                self._assignment_service.assign(assignment.target_id, assignment.profile_id)
                imported.append(assignment.target_id)
            except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError:
                failed.append(assignment.target_id)

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentImportResult(
            imported=tuple(imported),
            skipped=tuple(skipped),
            failed=tuple(failed),
        )

    def _build_export(
        self,
        assignments,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentExport:
        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentExport(
            exported_at=datetime.now(timezone.utc),
            assignments=assignments,
            metadata={"target_count": len(assignments)},
        )
