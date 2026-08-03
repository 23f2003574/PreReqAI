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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonService as BranchComparisonService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchHealthReport as BranchHealthReport,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchHealthStatus as BranchHealthStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetrics as BranchMetrics,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError as BranchMetricsError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsService as BranchMetricsService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchService as BranchService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSynchronizationService as BranchSynchronizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation as ChangeOperation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetService as ChangeSetService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictService as ConflictService,
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


class _StubVersion:
    def __init__(self, version, created_at):
        self.version = version
        self.created_at = created_at


class _StubVersionService:
    def __init__(self, mapping):
        self._mapping = mapping

    def find(self, workspace_id, version):
        return self._mapping.get((workspace_id, version))


def _build():
    binding_service = BindingRegistryService()
    template_service = TemplateRegistryService()
    preset_service = PresetRegistryService()
    group_service = GroupRegistryService()

    for binding_id in ("binding-1", "binding-2", "binding-3"):
        binding_service.register(_binding(binding_id))

    workspace_service = WorkspaceService(binding_service, template_service, preset_service, group_service)
    workspace_service.create(_workspace("workspace-1", binding_ids=("binding-1",)))
    workspace_service.create(_workspace("workspace-2", binding_ids=()))

    version_service = VersionService(workspace_service)
    change_set_service = ChangeSetService(workspace_service)
    conflict_service = ConflictService(change_set_service, workspace_service)
    branch_service = BranchService(workspace_service, version_service)
    sync_service = BranchSynchronizationService(
        branch_service, change_set_service, version_service, conflict_service
    )
    metrics_service = BranchMetricsService(
        branch_service, change_set_service, conflict_service, sync_service, version_service
    )

    return {
        "workspace_service": workspace_service,
        "version_service": version_service,
        "change_set_service": change_set_service,
        "conflict_service": conflict_service,
        "branch_service": branch_service,
        "sync_service": sync_service,
        "metrics_service": metrics_service,
    }


class TestBindingWorkspaceBranchMetricsService:
    def test_metrics_calculation(self):
        services = _build()
        branch_service = services["branch_service"]
        metrics_service = services["metrics_service"]

        branch = branch_service.create("workspace-1", "feature-x").branch

        metrics = metrics_service.calculate(branch.branch_id)

        assert isinstance(metrics, BranchMetrics)
        assert metrics.branch_id == branch.branch_id
        assert metrics.change_set_count == 0
        assert metrics.conflict_count == 0
        assert metrics.days_since_sync == 0
        assert metrics.health_score == 100

        with pytest.raises(BranchMetricsError):
            metrics_service.calculate("unknown-branch")

    def test_conflict_scoring(self):
        services = _build()
        branch_service = services["branch_service"]
        change_set_service = services["change_set_service"]
        metrics_service = services["metrics_service"]

        branch = branch_service.create("workspace-1", "feature-x").branch

        # binding-1 is already a member of workspace-1: both stale (conflicting)
        change_set = change_set_service.create("workspace-1", "stale adds")
        change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-1")
        )

        metrics = metrics_service.calculate(branch.branch_id)

        assert metrics.change_set_count == 1
        assert metrics.conflict_count == 1
        assert metrics.health_score == 100 - (25 * 1) - (3 * 1)

        assert metrics_service.health(branch.branch_id) == BranchHealthStatus.AT_RISK

    def test_health_report_generation(self):
        services = _build()
        branch_service = services["branch_service"]
        change_set_service = services["change_set_service"]
        metrics_service = services["metrics_service"]

        healthy_branch = branch_service.create("workspace-1", "healthy").branch

        risky_branch = branch_service.create("workspace-1", "risky").branch
        change_set = change_set_service.create("workspace-1", "stale adds")
        change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-1")
        )

        report = metrics_service.report("workspace-1")

        assert isinstance(report, BranchHealthReport)
        assert report.generated_at is not None
        assert {m.branch_id for m in report.branch_metrics} == {
            healthy_branch.branch_id,
            risky_branch.branch_id,
        }
        assert any(
            risky_branch.branch_id in recommendation and "conflict" in recommendation
            for recommendation in report.recommendations
        )

    def test_workspace_report(self):
        services = _build()
        branch_service = services["branch_service"]
        metrics_service = services["metrics_service"]

        # an empty workspace still produces a valid, empty report
        report = metrics_service.report("workspace-2")
        assert report.branch_metrics == ()
        assert report.recommendations == ()

        branch_service.create("workspace-2", "feature-x")
        populated_report = metrics_service.report("workspace-2")
        assert len(populated_report.branch_metrics) == 1

        with pytest.raises(BranchMetricsError):
            metrics_service.report("unknown-workspace")

    def test_stale_branch_detection(self):
        services = _build()
        workspace_service = services["workspace_service"]
        version_service = services["version_service"]
        change_set_service = services["change_set_service"]
        conflict_service = services["conflict_service"]
        branch_service = services["branch_service"]
        sync_service = services["sync_service"]

        version_service.publish("workspace-1", "v1")
        stale_branch = branch_service.create("workspace-1", "stale").branch

        fresh_branch = branch_service.create("workspace-2", "fresh").branch

        old_timestamp = datetime.now(timezone.utc) - timedelta(days=20)
        stub_version_service = _StubVersionService({("workspace-1", "v1"): _StubVersion("v1", old_timestamp)})

        backdated_metrics_service = BranchMetricsService(
            branch_service, change_set_service, conflict_service, sync_service, stub_version_service
        )

        stale_metrics = backdated_metrics_service.calculate(stale_branch.branch_id)
        assert stale_metrics.days_since_sync >= 20

        fresh_metrics = backdated_metrics_service.calculate(fresh_branch.branch_id)
        assert fresh_metrics.days_since_sync == 0

        stale = backdated_metrics_service.stale_branches("workspace-1")
        assert [m.branch_id for m in stale] == [stale_branch.branch_id]

        assert backdated_metrics_service.stale_branches("workspace-2") == ()

    def test_invalid_input_rejection(self):
        services = _build()
        metrics_service = services["metrics_service"]

        with pytest.raises(BranchMetricsError):
            metrics_service.calculate("   ")

        with pytest.raises(BranchMetricsError):
            metrics_service.health("   ")

        with pytest.raises(BranchMetricsError):
            metrics_service.report("   ")

        with pytest.raises(BranchMetricsError):
            metrics_service.stale_branches("   ")

        with pytest.raises(BranchMetricsError):
            metrics_service.calculate("unknown-branch")

        with pytest.raises(BranchMetricsError):
            metrics_service.health("unknown-branch")

        with pytest.raises(BranchMetricsError):
            BranchMetrics(
                branch_id="branch-1",
                change_set_count=-1,
                conflict_count=0,
                days_since_sync=0,
                health_score=100,
            )

        with pytest.raises(BranchMetricsError):
            BranchMetrics(
                branch_id="branch-1",
                change_set_count=0,
                conflict_count=0,
                days_since_sync=0,
                health_score=150,
            )

        with pytest.raises(BranchMetricsError):
            BranchMetrics(
                branch_id="   ",
                change_set_count=0,
                conflict_count=0,
                days_since_sync=0,
                health_score=100,
            )

    def test_reject_invalid_constructor_arguments(self):
        services = _build()

        with pytest.raises(BranchMetricsError):
            BranchMetricsService(
                None,
                services["change_set_service"],
                services["conflict_service"],
                services["sync_service"],
                services["version_service"],
            )

        with pytest.raises(BranchMetricsError):
            BranchMetricsService(
                services["branch_service"],
                None,
                services["conflict_service"],
                services["sync_service"],
                services["version_service"],
            )

        with pytest.raises(BranchMetricsError):
            BranchMetricsService(
                services["branch_service"],
                services["change_set_service"],
                None,
                services["sync_service"],
                services["version_service"],
            )

        with pytest.raises(BranchMetricsError):
            BranchMetricsService(
                services["branch_service"],
                services["change_set_service"],
                services["conflict_service"],
                None,
                services["version_service"],
            )

        with pytest.raises(BranchMetricsError):
            BranchMetricsService(
                services["branch_service"],
                services["change_set_service"],
                services["conflict_service"],
                services["sync_service"],
                None,
            )

    def test_integration_with_comparison_workflow(self):
        services = _build()
        workspace_service = services["workspace_service"]
        change_set_service = services["change_set_service"]
        branch_service = services["branch_service"]
        metrics_service = services["metrics_service"]

        comparison_service = BranchComparisonService(branch_service, workspace_service, change_set_service)

        branch_a = branch_service.create("workspace-1", "branch-a").branch
        branch_b = branch_service.create("workspace-2", "branch-b").branch

        # binding-1 is a member of workspace-1 only; staging a redundant add
        # against it makes it both a metrics conflict and a comparison
        # difference, since they share the same underlying detection
        change_set = change_set_service.create("workspace-1", "touch binding-1")
        change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-1")
        )

        metrics = metrics_service.calculate(branch_a.branch_id)
        assert metrics.conflict_count == 1

        comparison = comparison_service.compare(branch_a.branch_id, branch_b.branch_id)
        assert any(difference.resource_id == "binding-1" for difference in comparison.differences)
