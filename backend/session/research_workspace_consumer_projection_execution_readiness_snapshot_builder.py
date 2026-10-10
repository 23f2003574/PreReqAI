from .research_workspace_consumer_projection_execution_lifecycle_report import (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleReport,
)

from .research_workspace_consumer_projection_execution_readiness_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshot,
)

from .research_workspace_consumer_projection_execution_readiness_snapshot_error import (
    ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotError,
)

from .research_workspace_consumer_projection_execution_summary import (
    ResearchWorkspaceConsumerProjectionExecutionSummary,
)


class ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotBuilder:
    """
    Validates and composes an existing execution lifecycle report
    and execution summary into one immutable execution readiness
    snapshot.

    The builder's responsibility is validation and composition, not
    recalculation or repair. It does NOT re-run lifecycle
    resolution, recalculate the summary, access repositories, or
    derive new policy.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same snapshot
    - Side-effect free: Never mutates any input artifact
    """

    def build(
        self,
        lifecycle: ResearchWorkspaceConsumerProjectionExecutionLifecycleReport,
        summary: ResearchWorkspaceConsumerProjectionExecutionSummary,
    ) -> ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshot:
        """
        Build an execution readiness snapshot from an execution
        lifecycle report and execution summary.

        Args:
            lifecycle: The execution lifecycle report for this
                projection
            summary: The execution summary describing the same
                projection

        Returns:
            An immutable execution readiness snapshot

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotError:
                If the lifecycle report and summary do not describe
                the same projection
        """

        if summary.projection_name != lifecycle.projection_name:
            raise ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotError(
                f"Cannot build an execution readiness snapshot: summary "
                f"projection name '{summary.projection_name}' does not "
                f"match lifecycle projection name "
                f"'{lifecycle.projection_name}'"
            )

        return ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshot(
            projection_name=lifecycle.projection_name,
            lifecycle_state=lifecycle.state,
            reason=lifecycle.reason,
            ready_for_execution=lifecycle.active,
            summary=summary.description,
        )
