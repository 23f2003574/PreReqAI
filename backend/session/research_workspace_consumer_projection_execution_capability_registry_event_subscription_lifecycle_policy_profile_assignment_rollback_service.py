from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_audit_record import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditRecord,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_rollback_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_rollback_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_rollback_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackService:
    """
    Safely rolls a consumer projection execution capability registry
    event subscription lifecycle policy profile assignment target
    back to a state recorded in its audit history.

    The service's responsibility is orchestrating rollback, not
    assignment, unassignment, or audit recording themselves. It does
    NOT assign or unassign profiles outside of a rollback, mutate or
    remove prior audit records, log, or publish events. It operates
    over an assignment service and an audit service supplied at
    construction time, since both carry state that must already
    reflect prior assignments and their history.

    The service is:
    - Non-destructive: A rollback is recorded as a new, append-only
      audit entry; no prior audit record is ever modified or removed
    - Idempotent: Rolling back to a state the target is already in
      restores nothing and appends no new audit entry
    """

    def __init__(
        self,
        assignment_service,
        audit_service,
    ):
        """
        Args:
            assignment_service: The service used to read and apply
                the active assignment
            audit_service: The service recording and querying
                assignment audit history
        """

        self._assignment_service = assignment_service
        self._audit_service = audit_service

    def rollback(
        self,
        request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackRequest,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackResult:
        """
        Restore a target's assignment to the state recorded by a
        specific audit record.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError:
                If the request is None, has a blank target ID or
                audit ID, the target ID is unknown, no audit record
                exists under the audit ID, or the audit ID belongs to
                a different target
        """

        record = self._resolve_audit_record(request)

        previous_assignment = self._assignment_service.find(request.target_id)

        if self._already_at_state(previous_assignment, record):
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackResult(
                previous_assignment=previous_assignment,
                restored_assignment=previous_assignment,
                successful=True,
            )

        if record.profile_id is not None:
            restored_assignment = self._assignment_service.assign(request.target_id, record.profile_id).assignment
        else:
            self._assignment_service.unassign(request.target_id)
            restored_assignment = None

        self._audit_service.record(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditRecord(
                audit_id=str(uuid4()),
                target_id=request.target_id,
                profile_id=record.profile_id,
                operation="assign" if record.profile_id is not None else "unassign",
                timestamp=datetime.now(timezone.utc),
            )
        )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackResult(
            previous_assignment=previous_assignment,
            restored_assignment=restored_assignment,
            successful=True,
        )

    def can_rollback(self, target_id: str) -> bool:
        """
        Check whether a target currently has any audit history to
        roll back to.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError:
                If target_id is None or blank
        """

        self._validate_id(target_id, "target ID")

        return len(self._audit_service.history(target_id).records) > 0

    def rollback_history(self, target_id: str) -> tuple:
        """
        List every audit record for a target, in chronological order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError:
                If target_id is None or blank
        """

        self._validate_id(target_id, "target ID")

        return self._audit_service.history(target_id).records

    def _resolve_audit_record(self, request):
        if request is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError(
                "Cannot roll back from a None request."
            )

        if not isinstance(
            request,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackRequest,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError(
                "Cannot roll back: request must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackRequest."
            )

        target_history = self._audit_service.history(request.target_id).records

        if not target_history:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError(
                f"Cannot roll back: target ID {request.target_id!r} is unknown."
            )

        for record in target_history:
            if record.audit_id == request.audit_id:
                return record

        for record in self._audit_service.list():
            if record.audit_id == request.audit_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError(
                    f"Cannot roll back: audit ID {request.audit_id!r} does not belong to target ID {request.target_id!r}."
                )

        raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError(
            f"Cannot roll back: no audit record found for audit ID {request.audit_id!r}."
        )

    def _already_at_state(self, current_assignment, record) -> bool:
        if current_assignment is None:
            return record.profile_id is None

        return current_assignment.profile_id == record.profile_id

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError(
                f"Cannot roll back with an empty or blank {label}."
            )
