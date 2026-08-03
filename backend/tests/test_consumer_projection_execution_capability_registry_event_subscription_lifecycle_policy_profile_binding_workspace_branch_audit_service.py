from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding as Binding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService as GroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService as PresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService as BindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService as TemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace as Workspace,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveService as BranchArchiveService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError as AuditError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditEvent as AuditEvent,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditService as AuditService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchService as BranchService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTimeline as BranchTimeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation as ChangeOperation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy as ApprovalPolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewService as ReviewService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetService as ChangeSetService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictService as ConflictService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeService as MergeService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService as WorkspaceService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionService as VersionService,
)


def _binding(binding_id):
    return Binding(
        binding_id=binding_id,
        profile_id="development",
        capability_id="capability-a",
        created_at=datetime.now(timezone.utc),
    )


def _workspace(workspace_id, binding_ids=()):
    return Workspace(
        workspace_id=workspace_id,
        name=workspace_id,
        description="A workspace.",
        binding_ids=binding_ids,
        template_ids=(),
        preset_ids=(),
        group_ids=(),
    )


def _operation(operation_id, operation_type, resource_type, resource_id):
    return ChangeOperation(
        operation_id=operation_id,
        operation_type=operation_type,
        resource_type=resource_type,
        resource_id=resource_id,
    )


def _event(event_id, branch_id, event_type, timestamp, actor="system", metadata=None):
    return AuditEvent(
        event_id=event_id,
        branch_id=branch_id,
        event_type=event_type,
        actor=actor,
        timestamp=timestamp,
        metadata=metadata if metadata is not None else {},
    )


class TestBindingWorkspaceBranchAuditService:
    def test_record_audit_event(self):
        service = AuditService()

        event = _event("event-1", "branch-a", "edit", datetime.now(timezone.utc))
        service.record(event)

        assert service.list() == (event,)

    def test_retrieve_timeline(self):
        service = AuditService()

        base = datetime.now(timezone.utc)
        first = _event("event-1", "branch-a", "edit", base)
        second = _event("event-2", "branch-a", "review", base + timedelta(seconds=5))
        other = _event("event-3", "branch-b", "edit", base + timedelta(seconds=1))

        service.record(second)
        service.record(first)
        service.record(other)

        timeline = service.timeline("branch-a")

        assert isinstance(timeline, BranchTimeline)
        assert timeline.branch_id == "branch-a"
        assert timeline.events == (first, second)

        with pytest.raises(AuditError):
            service.timeline("   ")

    def test_timeline_ordering(self):
        service = AuditService()

        base = datetime.now(timezone.utc)
        first = _event("event-1", "branch-a", "edit", base + timedelta(seconds=10))
        second = _event("event-2", "branch-a", "review", base)
        third = _event("event-3", "branch-a", "merge", base + timedelta(seconds=5))

        service.record(first)
        service.record(second)
        service.record(third)

        timeline = service.timeline("branch-a")

        assert [event.event_id for event in timeline.events] == ["event-2", "event-3", "event-1"]

    def test_latest_event(self):
        service = AuditService()

        base = datetime.now(timezone.utc)
        first = _event("event-1", "branch-a", "edit", base)
        second = _event("event-2", "branch-a", "rebase", base + timedelta(seconds=5))

        service.record(first)
        service.record(second)

        assert service.latest("branch-a") == second
        assert service.latest("branch-unknown") is None

    def test_filter_by_event_type(self):
        service = AuditService()

        base = datetime.now(timezone.utc)
        edit_event = _event("event-1", "branch-a", "edit", base)
        review_event = _event("event-2", "branch-a", "review", base + timedelta(seconds=5))
        another_review = _event("event-3", "branch-a", "review", base + timedelta(seconds=10))

        service.record(edit_event)
        service.record(review_event)
        service.record(another_review)

        reviews = service.events("branch-a", "review")
        assert reviews == (review_event, another_review)

        merges = service.events("branch-a", "merge")
        assert merges == ()

        with pytest.raises(AuditError):
            service.events("branch-a", "not_a_real_type")

        with pytest.raises(AuditError):
            service.events("branch-a", "   ")

    def test_purge_expired_events(self):
        service = AuditService()

        base = datetime.now(timezone.utc)
        old = _event("event-1", "branch-a", "edit", base - timedelta(days=2))
        recent = _event("event-2", "branch-a", "review", base)

        service.record(old)
        service.record(recent)

        purged_count = service.purge(base - timedelta(days=1))

        assert purged_count == 1
        assert service.list() == (recent,)

        with pytest.raises(AuditError):
            service.purge(None)

    def test_duplicate_event_rejection(self):
        service = AuditService()

        first = _event("event-1", "branch-a", "edit", datetime.now(timezone.utc))
        duplicate = _event("event-1", "branch-b", "review", datetime.now(timezone.utc))

        service.record(first)

        with pytest.raises(AuditError):
            service.record(duplicate)

    def test_reject_invalid_events(self):
        with pytest.raises(AuditError):
            _event("   ", "branch-a", "edit", datetime.now(timezone.utc))

        with pytest.raises(AuditError):
            _event("event-1", None, "edit", datetime.now(timezone.utc))

        with pytest.raises(AuditError):
            _event("event-1", "branch-a", "not_a_real_type", datetime.now(timezone.utc))

        with pytest.raises(AuditError):
            _event("event-1", "branch-a", "edit", None)

        with pytest.raises(AuditError):
            _event("event-1", "branch-a", "edit", datetime.now(timezone.utc), actor="   ")

        with pytest.raises(AuditError):
            AuditEvent(
                event_id="event-1",
                branch_id="branch-a",
                event_type="edit",
                actor="system",
                timestamp=datetime.now(timezone.utc),
                metadata="not-a-mapping",
            )

        service = AuditService()

        with pytest.raises(AuditError):
            service.record(None)

    def test_reject_invalid_timeline_construction(self):
        event = _event("event-1", "branch-a", "edit", datetime.now(timezone.utc))

        with pytest.raises(AuditError):
            BranchTimeline(branch_id="branch-b", events=(event,))

        with pytest.raises(AuditError):
            BranchTimeline(branch_id="   ", events=())

    def test_immutable_timeline_and_events(self):
        service = AuditService()

        event = _event("event-1", "branch-a", "edit", datetime.now(timezone.utc))
        service.record(event)

        timeline = service.timeline("branch-a")

        with pytest.raises(AttributeError):
            timeline.events = ()

        with pytest.raises(AttributeError):
            event.event_type = "review"

    def test_integrates_with_merge_and_review_workflows(self):
        binding_service = BindingRegistryService()
        template_service = TemplateRegistryService()
        preset_service = PresetRegistryService()
        group_service = GroupRegistryService()

        binding_service.register(_binding("binding-1"))

        workspace_service = WorkspaceService(binding_service, template_service, preset_service, group_service)
        workspace_service.create(_workspace("workspace-1", binding_ids=()))

        version_service = VersionService(workspace_service)
        change_set_service = ChangeSetService(workspace_service)
        policy = ApprovalPolicy(minimum_approvals=1, require_unanimous=False)
        review_service = ReviewService(change_set_service, policy)
        conflict_service = ConflictService(change_set_service, workspace_service)
        merge_service = MergeService(change_set_service, review_service, conflict_service)
        branch_service = BranchService(workspace_service, version_service)
        archive_service = BranchArchiveService(branch_service)
        audit_service = AuditService()

        branch = branch_service.create("workspace-1", "feature-x").branch

        change_set = change_set_service.create(branch.workspace_id, "add binding-1")
        change_set = change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-1")
        )
        audit_service.record(
            _event(
                "event-1",
                branch.branch_id,
                "edit",
                datetime.now(timezone.utc),
                actor="dev-a",
                metadata={"change_set_id": change_set.change_set_id},
            )
        )

        review = review_service.submit(change_set.change_set_id, "reviewer-a")
        review_service.approve(review.review_id)
        audit_service.record(
            _event(
                "event-2",
                branch.branch_id,
                "review",
                datetime.now(timezone.utc),
                actor="reviewer-a",
                metadata={"review_id": review.review_id, "outcome": "approved"},
            )
        )

        merge_result = merge_service.merge([change_set.change_set_id])
        assert merge_result.successful is True
        audit_service.record(
            _event(
                "event-3",
                branch.branch_id,
                "merge",
                datetime.now(timezone.utc),
                actor="dev-a",
                metadata={"operation_count": len(merge_result.merged_operations)},
            )
        )

        archive_service.archive(branch.branch_id, reason="feature shipped")
        audit_service.record(
            _event(
                "event-4",
                branch.branch_id,
                "recovery",
                datetime.now(timezone.utc),
                actor="dev-a",
                metadata={"action": "archived"},
            )
        )

        timeline = audit_service.timeline(branch.branch_id)

        assert [event.event_type for event in timeline.events] == [
            "edit",
            "review",
            "merge",
            "recovery",
        ]
        assert timeline.events[1].metadata["review_id"] == review.review_id
        assert timeline.events[2].metadata["operation_count"] == 1
