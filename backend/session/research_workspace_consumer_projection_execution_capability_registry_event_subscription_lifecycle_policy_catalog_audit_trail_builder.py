from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_audit_operation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditOperation,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_audit_trail import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrail,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_audit_trail_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder:
    """
    Builds and extends an immutable audit trail of operations
    performed against a consumer projection execution capability
    registry event subscription lifecycle policy catalog.

    The builder's responsibility is validation and assembly of
    audit entries, not recording, catalog construction, or
    evaluation. It does NOT build catalogs, evaluate policies,
    execute lifecycle transitions, mutate its inputs, persist audit
    trails, log, or publish events.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same entries always produce the same audit
      trail
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        entries,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrail:
        """
        Build an audit trail from a collection of audit entries.

        Args:
            entries: The audit entries to assemble, in the order
                they should appear in the audit trail

        Returns:
            An immutable audit trail preserving insertion order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError:
                If the entries are None, any entry is None, any
                entry's operation is not a recognized audit
                operation, any entry's timestamp is missing, or
                sequence numbers are not strictly increasing
        """

        if entries is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError(
                    "Cannot build an audit trail with None entries."
                )
            )

        entries = tuple(
            entries
        )

        self._validate_entries(
            entries
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrail(
                entries=entries,

                total_entries=len(
                    entries
                ),
            )
        )

    def append(

        self,

        audit_trail,

        entry,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrail:
        """
        Append a single audit entry to an existing audit trail,
        producing a new audit trail.

        Args:
            audit_trail: The existing audit trail to extend
            entry: The audit entry to append

        Returns:
            A new immutable audit trail with the entry appended;
            the original audit trail is left unchanged

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError:
                If the audit trail or entry is None, the entry's
                operation is not a recognized audit operation, the
                entry's timestamp is missing, or the entry's
                sequence number does not strictly increase on the
                audit trail's last sequence number
        """

        if audit_trail is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError(
                    "Cannot append to a None audit trail."
                )
            )

        if entry is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError(
                    "Cannot append a None audit entry."
                )
            )

        updated_entries = audit_trail.entries + (
            entry,
        )

        self._validate_entries(
            updated_entries
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrail(
                entries=updated_entries,

                total_entries=len(
                    updated_entries
                ),
            )
        )

    def _validate_entries(

        self,

        entries,

    ) -> None:

        last_sequence_number = None

        for entry in entries:

            if entry is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError(
                        "Cannot build an audit trail with a None entry."
                    )
                )

            if not isinstance(

                entry.operation,

                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditOperation,
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError(
                        f"Cannot build an audit trail with an invalid operation: "
                        f"{entry.operation!r}."
                    )
                )

            if entry.timestamp is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError(
                        "Cannot build an audit trail with a missing timestamp for "
                        f"sequence number {entry.sequence_number!r}."
                    )
                )

            if (

                last_sequence_number is not None

                and entry.sequence_number <= last_sequence_number
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError(
                        "Cannot build an audit trail with a non-increasing "
                        f"sequence number: {entry.sequence_number!r} does not "
                        f"follow {last_sequence_number!r}."
                    )
                )

            last_sequence_number = entry.sequence_number
