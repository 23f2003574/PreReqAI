from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackService,
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
    audit_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditService()

    rollback_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackService(
        assignment_service,
        audit_service,
    )

    return rollback_service, assignment_service, audit_service


def _record(audit_id, target_id, profile_id, operation, timestamp):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentAuditRecord(
        audit_id=audit_id,
        target_id=target_id,
        profile_id=profile_id,
        operation=operation,
        timestamp=timestamp,
    )


class TestProfileAssignmentRollbackService:
    def test_successful_rollback(self):
        rollback_service, assignment_service, audit_service = _build_service()

        base = datetime.now(timezone.utc)
        audit_service.record(_record("audit-1", "target-a", "development", "assign", base))

        assignment_service.assign("target-a", "development")
        assignment_service.assign("target-a", "staging")

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackRequest(
            target_id="target-a",
            audit_id="audit-1",
        )

        result = rollback_service.rollback(request)

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackResult)
        assert result.successful is True
        assert result.previous_assignment.profile_id == "staging"
        assert result.restored_assignment.profile_id == "development"
        assert assignment_service.find("target-a").profile_id == "development"

    def test_rollback_eligibility(self):
        rollback_service, assignment_service, audit_service = _build_service()

        assert rollback_service.can_rollback("target-a") is False

        audit_service.record(
            _record("audit-1", "target-a", "development", "assign", datetime.now(timezone.utc))
        )

        assert rollback_service.can_rollback("target-a") is True

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError):
            rollback_service.can_rollback("   ")

    def test_rollback_history(self):
        rollback_service, _, audit_service = _build_service()

        base = datetime.now(timezone.utc)
        first = _record("audit-1", "target-a", "development", "assign", base)
        second = _record("audit-2", "target-a", "staging", "assign", base + timedelta(seconds=5))

        audit_service.record(second)
        audit_service.record(first)

        history = rollback_service.rollback_history("target-a")

        assert history == (first, second)

    def test_audit_entry_created(self):
        rollback_service, assignment_service, audit_service = _build_service()

        base = datetime.now(timezone.utc)
        audit_service.record(_record("audit-1", "target-a", "development", "assign", base))

        assignment_service.assign("target-a", "development")
        assignment_service.assign("target-a", "staging")

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackRequest(
            target_id="target-a",
            audit_id="audit-1",
        )

        rollback_service.rollback(request)

        history = audit_service.history("target-a").records

        assert len(history) == 2
        newest = history[-1]
        assert newest.target_id == "target-a"
        assert newest.profile_id == "development"
        assert newest.operation == "assign"
        assert newest.audit_id != "audit-1"

    def test_idempotent_rollback(self):
        rollback_service, assignment_service, audit_service = _build_service()

        base = datetime.now(timezone.utc)
        audit_service.record(_record("audit-1", "target-a", "development", "assign", base))
        assignment_service.assign("target-a", "development")

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackRequest(
            target_id="target-a",
            audit_id="audit-1",
        )

        result = rollback_service.rollback(request)

        assert result.successful is True
        assert result.previous_assignment.profile_id == "development"
        assert result.restored_assignment.profile_id == "development"
        assert len(audit_service.history("target-a").records) == 1

    def test_invalid_rollback_rejection(self):
        rollback_service, assignment_service, audit_service = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackRequest(
                target_id="   ",
                audit_id="audit-1",
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError):
            rollback_service.rollback(None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackRequest(
                    target_id="target-unknown",
                    audit_id="audit-1",
                )
            )

        audit_service.record(
            _record("audit-1", "target-a", "development", "assign", datetime.now(timezone.utc))
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackRequest(
                    target_id="target-a",
                    audit_id="audit-missing",
                )
            )

        audit_service.record(
            _record("audit-2", "target-b", "staging", "assign", datetime.now(timezone.utc))
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackRequest(
                    target_id="target-a",
                    audit_id="audit-2",
                )
            )

    def test_immutable_rollback_result(self):
        rollback_service, assignment_service, audit_service = _build_service()

        audit_service.record(
            _record("audit-1", "target-a", "development", "assign", datetime.now(timezone.utc))
        )
        assignment_service.assign("target-a", "development")

        result = rollback_service.rollback(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackRequest(
                target_id="target-a",
                audit_id="audit-1",
            )
        )

        with pytest.raises(AttributeError):
            result.successful = False
