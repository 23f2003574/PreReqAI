from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_audit_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditHistory,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditService:
    """
    Tracks every consumer projection execution capability registry
    event subscription lifecycle policy profile binding template
    lifecycle operation for traceability, debugging, and compliance,
    without altering the template's operational state.

    The service's responsibility is recording and retrieving audit
    records, not creating templates, managing membership,
    instantiating, deploying, releasing, synchronizing, or otherwise
    affecting template state. It does NOT mutate an existing audit
    record, persist records externally, log, or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Append-only: Records are never mutated or replaced once
      recorded, only added or purged
    - Duplicate-free: No two recorded audit records may share an
      audit ID
    - Chronological: history(), latest(), and list() always order
      records by timestamp, regardless of recording order
    """

    def __init__(self):
        self._records = ()
        self._lock = RLock()

    def record(
        self,
        record,
    ) -> None:
        """
        Append an audit record to the log.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError:
                If record is None or its audit ID is already recorded
        """

        if record is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError(
                "Cannot record a None audit record."
            )

        with self._lock:
            if any(existing.audit_id == record.audit_id for existing in self._records):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError(
                    f"Audit ID {record.audit_id!r} is already recorded."
                )

            self._records = self._records + (record,)

    def history(
        self,
        template_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditHistory:
        """
        Retrieve every audit record for a template, in chronological
        order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError:
                If template_id is None or blank
        """

        self._validate_template_id(template_id)

        with self._lock:
            matching = tuple(
                sorted(
                    (existing for existing in self._records if existing.template_id == template_id),
                    key=lambda existing: existing.timestamp,
                )
            )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditHistory(
            records=matching,
        )

    def latest(self, template_id: str):
        """
        Retrieve the most recent audit record for a template.

        Returns:
            The most recent audit record for template_id, or None if
            no record has been recorded for it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError:
                If template_id is None or blank
        """

        self._validate_template_id(template_id)

        with self._lock:
            matching = [existing for existing in self._records if existing.template_id == template_id]

        if not matching:
            return None

        return max(matching, key=lambda existing: existing.timestamp)

    def list(self) -> tuple:
        """
        List every recorded audit record, in chronological order.
        """

        with self._lock:
            return tuple(sorted(self._records, key=lambda existing: existing.timestamp))

    def purge(self, before_timestamp) -> int:
        """
        Remove every audit record older than before_timestamp.

        Args:
            before_timestamp: Records with a timestamp strictly
                earlier than this are removed; records at or after
                this timestamp are preserved

        Returns:
            The number of audit records removed

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError:
                If before_timestamp is None
        """

        if before_timestamp is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError(
                "Cannot purge with a None timestamp."
            )

        with self._lock:
            retained = tuple(
                existing for existing in self._records if existing.timestamp >= before_timestamp
            )

            purged_count = len(self._records) - len(retained)

            self._records = retained

            return purged_count

    def _validate_template_id(self, template_id: str) -> None:
        if template_id is None or not template_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError(
                "Cannot perform an audit lookup with an empty or blank template ID."
            )
