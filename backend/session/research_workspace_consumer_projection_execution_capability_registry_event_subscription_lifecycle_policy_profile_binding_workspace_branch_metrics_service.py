from datetime import (
    datetime,
    timezone,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_health_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchHealthReport,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_health_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchHealthStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_metrics import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetrics,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_metrics_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_sync_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_conflict_resolution_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus,
)

_CONFLICT_PENALTY = 25
_STALE_PENALTY_PER_DAY = 2
_CHANGE_SET_PENALTY = 3

_HEALTHY_THRESHOLD = 80
_AT_RISK_THRESHOLD = 50

_STALE_THRESHOLD_DAYS = 14
_HIGH_CHANGE_SET_COUNT_THRESHOLD = 3


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsService:
    """
    Computes health analytics for consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace branches, so stale, risky, or high-conflict
    branches can be identified before merge.

    The service's responsibility is metrics computation, health
    classification, and reporting, not branch creation, checkout,
    renaming, or closing, or change set, conflict, or synchronization
    management themselves. It does NOT create, checkout, rename, or
    close a branch, create or resolve change sets or conflicts, or
    synchronize a branch. Every metric is computed fresh from a change
    set service, a conflict service, a synchronization service, and a
    workspace version service supplied at construction time, so it
    integrates with the conflict, comparison, and synchronization
    workflows without duplicating their state: conflict_count reuses
    the same conflict detection the comparison engine's has_conflicts()
    is built on, and days_since_sync reuses synchronization history.

    A branch's health score starts at 100 and is reduced by 25 points
    per unresolved conflict, 2 points per day since its last
    synchronization, and 3 points per open change set staged against
    its workspace, floored at 0. A score of 80 or above is "healthy",
    50 up to but excluding 80 is "at_risk", and anything below 50 is
    "critical".

    The service is:
    - Stateless: Every call recomputes metrics from its dependencies;
      nothing is cached or retained between calls
    - Deterministic: The same underlying state always produces the
      same metrics and classification
    - Read-only: Computing metrics, health, or a report never mutates
      a branch, a change set, a conflict, or synchronization state
    """

    def __init__(self, branch_service, change_set_service, conflict_service, sync_service, workspace_version_service):
        """
        Args:
            branch_service: The service used to resolve a branch's
                workspace ID and base revision, and to list every
                branch on a workspace. Any object exposing
                `find(branch_id)` and `list(workspace_id)` is accepted
            change_set_service: The service used to enumerate the
                change sets staged against a branch's workspace. Any
                object exposing `list()` is accepted
            conflict_service: The service used to detect conflicts on
                a change set. Any object exposing
                `detect(change_set_id)` is accepted
            sync_service: The service used to resolve a branch's
                synchronization history. Any object exposing
                `sync_history(branch_id)` is accepted
            workspace_version_service: The service used to resolve
                when a revision was published. Any object exposing
                `find(workspace_id, version)` is accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError:
                If any dependency is None
        """

        for dependency, name in (
            (branch_service, "branch service"),
            (change_set_service, "change set service"),
            (conflict_service, "conflict service"),
            (sync_service, "branch synchronization service"),
            (workspace_version_service, "workspace version service"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError(
                    f"Cannot initialize branch metrics service with a None {name}."
                )

        self._branch_service = branch_service
        self._change_set_service = change_set_service
        self._conflict_service = conflict_service
        self._sync_service = sync_service
        self._workspace_version_service = workspace_version_service

    def calculate(
        self,
        branch_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetrics:
        """
        Compute a branch's current health metrics.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError:
                If branch_id is None or blank, or no branch is
                registered under it
        """

        self._validate_id(branch_id, "branch ID")

        branch = self._resolve_branch(branch_id)

        change_set_count = self._count_open_change_sets(branch.workspace_id)
        conflict_count = self._count_unresolved_conflicts(branch.workspace_id)
        days_since_sync = self._days_since_sync(branch)
        health_score = self._compute_health_score(change_set_count, conflict_count, days_since_sync)

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetrics(
            branch_id=branch_id,
            change_set_count=change_set_count,
            conflict_count=conflict_count,
            days_since_sync=days_since_sync,
            health_score=health_score,
        )

    def health(
        self,
        branch_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchHealthStatus:
        """
        Classify a branch's current health score.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError:
                If branch_id is None or blank, or no branch is
                registered under it
        """

        return self._classify(self.calculate(branch_id).health_score)

    def report(
        self,
        workspace_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchHealthReport:
        """
        Generate a health report covering every branch on a
        workspace.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError:
                If workspace_id is None or blank, or no workspace is
                registered under it
        """

        self._validate_id(workspace_id, "workspace ID")

        branches = self._resolve_branches(workspace_id)
        branch_metrics = tuple(self.calculate(branch.branch_id) for branch in branches)

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchHealthReport(
            generated_at=datetime.now(timezone.utc),
            branch_metrics=branch_metrics,
            recommendations=self._build_recommendations(branch_metrics),
        )

    def stale_branches(self, workspace_id: str) -> tuple:
        """
        List the metrics of every branch on a workspace that has not
        been synchronized within the staleness threshold.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError:
                If workspace_id is None or blank, or no workspace is
                registered under it
        """

        self._validate_id(workspace_id, "workspace ID")

        branches = self._resolve_branches(workspace_id)

        return tuple(
            metrics
            for metrics in (self.calculate(branch.branch_id) for branch in branches)
            if metrics.days_since_sync >= _STALE_THRESHOLD_DAYS
        )

    def _resolve_branches(self, workspace_id: str) -> tuple:
        try:
            return self._branch_service.list(workspace_id)
        except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError(
                str(error)
            ) from error

    def _build_recommendations(self, branch_metrics: tuple) -> tuple:
        recommendations = []

        for metrics in branch_metrics:
            if metrics.conflict_count > 0:
                recommendations.append(
                    f"Branch ID {metrics.branch_id!r} has {metrics.conflict_count} unresolved conflict(s); "
                    "resolve them before merging."
                )

            if metrics.days_since_sync >= _STALE_THRESHOLD_DAYS:
                recommendations.append(
                    f"Branch ID {metrics.branch_id!r} has not been synchronized in {metrics.days_since_sync} "
                    "day(s); synchronize it with the latest revision."
                )

            if metrics.change_set_count > _HIGH_CHANGE_SET_COUNT_THRESHOLD:
                recommendations.append(
                    f"Branch ID {metrics.branch_id!r} has {metrics.change_set_count} open change set(s); "
                    "consider merging soon to reduce backlog."
                )

        return tuple(recommendations)

    def _count_open_change_sets(self, workspace_id: str) -> int:
        return sum(
            1
            for change_set in self._change_set_service.list()
            if change_set.workspace_id == workspace_id
            and change_set.status
            == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus.OPEN
        )

    def _count_unresolved_conflicts(self, workspace_id: str) -> int:
        seen_conflict_ids = set()

        for change_set in self._change_set_service.list():
            if change_set.workspace_id != workspace_id:
                continue

            if change_set.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus.OPEN:
                continue

            for conflict in self._conflict_service.detect(change_set.change_set_id):
                if (
                    conflict.resolution_status
                    == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus.UNRESOLVED
                ):
                    seen_conflict_ids.add(conflict.conflict_id)

        return len(seen_conflict_ids)

    def _days_since_sync(self, branch) -> int:
        history = self._sync_service.sync_history(branch.branch_id)

        reference_revision = branch.base_revision

        for record in reversed(history):
            if record.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncStatus.SUCCEEDED:
                reference_revision = record.target_revision
                break

        if reference_revision is None:
            return 0

        version = self._workspace_version_service.find(branch.workspace_id, reference_revision)

        if version is None:
            return 0

        return max((datetime.now(timezone.utc) - version.created_at).days, 0)

    def _compute_health_score(self, change_set_count: int, conflict_count: int, days_since_sync: int) -> int:
        score = (
            100
            - (conflict_count * _CONFLICT_PENALTY)
            - (days_since_sync * _STALE_PENALTY_PER_DAY)
            - (change_set_count * _CHANGE_SET_PENALTY)
        )

        return max(0, min(100, score))

    def _classify(
        self,
        health_score: int,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchHealthStatus:
        if health_score >= _HEALTHY_THRESHOLD:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchHealthStatus.HEALTHY

        if health_score >= _AT_RISK_THRESHOLD:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchHealthStatus.AT_RISK

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchHealthStatus.CRITICAL

    def _resolve_branch(self, branch_id: str):
        branch = self._branch_service.find(branch_id)

        if branch is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError(
                f"Cannot compute branch metrics: no branch is registered under branch ID {branch_id!r}."
            )

        return branch

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError(
                f"Cannot compute branch metrics with an empty or blank {label}."
            )
