from datetime import (
    datetime,
    timezone,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_export import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupExport,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_import_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupImportResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_registry_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_serialization_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationService:
    """
    Exports and imports consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    groups, enabling backup, migration, and cross-environment
    deployment of group configurations.

    The service's responsibility is capturing and reconstructing
    group configurations, not group creation, membership management,
    version publication, release management, persisting exports
    externally, logging, or publishing events. It reads and writes
    only through the group registry and binding registry it was
    constructed with, so a group's version history and release
    records, held by other services, are never touched and remain
    exactly as they were.

    The service is:
    - Deterministic: export() always orders groups by group ID, so
      the same registry state always produces the same export
    - Metadata-preserving: Exported group records are carried through
      unchanged, never reconstructed or reformatted
    - Idempotent: Importing the same export more than once leaves
      already-synchronized groups untouched
    - Partial-failure tolerant: A group that fails to import does not
      prevent the rest of the export from being applied
    """

    def __init__(
        self,
        group_registry,
        binding_registry,
    ):
        """
        Args:
            group_registry: The registry used to read and apply
                groups. Any object exposing `find(group_id)`,
                `list()`, `register(group)`, and `replace(group)` is
                accepted
            binding_registry: The registry used to verify a
                referenced member binding exists. Any object exposing
                `contains(binding_id)` is accepted
        """

        if group_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError(
                "Cannot initialize serialization service with a None group registry."
            )

        if binding_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError(
                "Cannot initialize serialization service with a None binding registry."
            )

        self._group_registry = group_registry
        self._binding_registry = binding_registry

    def export(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupExport:
        """
        Export every currently registered group.

        Returns:
            An immutable export carrying every registered group,
            ordered deterministically by group ID
        """

        group_ids = sorted(group.group_id for group in self._group_registry.list())

        groups = tuple(
            group
            for group in (self._group_registry.find(group_id) for group_id in group_ids)
            if group is not None
        )

        return self._build_export(groups)

    def export_group(
        self,
        group_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupExport:
        """
        Export a single currently registered group.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError:
                If group_id is None/blank, or no group is registered
                under it
        """

        if group_id is None or not group_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError(
                "Cannot export with an empty or blank group ID."
            )

        group = self._group_registry.find(group_id)

        if group is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError(
                f"Cannot export group ID {group_id!r}: no group is registered under it."
            )

        return self._build_export((group,))

    def validate_import(
        self,
        export_data,
    ) -> bool:
        """
        Validate an export before importing it.

        Returns:
            True if the export is well-formed and every referenced
            member binding is known

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError:
                If export_data is None, is not a well-formed export,
                contains duplicate group IDs, references an unknown
                binding, or carries invalid metadata
        """

        if export_data is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError(
                "Cannot validate a None export."
            )

        if not isinstance(
            export_data,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupExport,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError(
                "Cannot validate malformed export data: expected a binding group export."
            )

        if not isinstance(export_data.metadata, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError(
                "Cannot validate an export with invalid metadata."
            )

        seen_group_ids = set()

        for group in export_data.groups:
            group_id = getattr(group, "group_id", None)
            group_name = getattr(group, "group_name", None)
            binding_ids = getattr(group, "binding_ids", None)

            if (
                group_id is None
                or not group_id.strip()
                or group_name is None
                or not group_name.strip()
                or binding_ids is None
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError(
                    "Cannot validate malformed export data: every group requires a group ID, "
                    "group name, and binding IDs."
                )

            if group_id in seen_group_ids:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError(
                    f"Cannot validate an export with a duplicate group ID {group_id!r}."
                )

            seen_group_ids.add(group_id)

            for binding_id in binding_ids:
                if not self._binding_registry.contains(binding_id):
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError(
                        f"Cannot validate an export referencing unknown binding ID {binding_id!r}."
                    )

        return True

    def import_groups(
        self,
        export_data,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupImportResult:
        """
        Import groups from an export, applying only the groups that
        changed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSerializationError:
                If export_data fails validate_import()
        """

        self.validate_import(export_data)

        imported = []
        skipped = []
        failed = []

        for group in export_data.groups:
            current = self._group_registry.find(group.group_id)

            if (
                current is not None
                and current.group_name == group.group_name
                and tuple(current.binding_ids) == tuple(group.binding_ids)
            ):
                skipped.append(group.group_id)
                continue

            try:
                if current is None:
                    self._group_registry.register(group)
                else:
                    self._group_registry.replace(group)

                imported.append(group.group_id)
            except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError:
                failed.append(group.group_id)

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupImportResult(
            imported=tuple(imported),
            skipped=tuple(skipped),
            failed=tuple(failed),
        )

    def _build_export(
        self,
        groups,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupExport:
        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupExport(
            exported_at=datetime.now(timezone.utc),
            groups=groups,
            metadata={"group_count": len(groups)},
        )
