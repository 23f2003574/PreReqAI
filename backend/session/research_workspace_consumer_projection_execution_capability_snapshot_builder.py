from .research_workspace_consumer_projection_execution_capability_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReport,
)

from .research_workspace_consumer_projection_execution_capability_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshot,
)

from .research_workspace_consumer_projection_execution_capability_snapshot_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotError,
)

from .research_workspace_consumer_projection_execution_capability_summary import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySummary,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotBuilder:
    """
    Validates and composes an existing execution capability report
    and capability summary into one immutable execution capability
    snapshot.

    The builder's responsibility is validation and composition, not
    recalculation or repair. It does NOT re-run capability
    resolution, recalculate the summary, access repositories, or
    derive new policy.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same snapshot
    - Side-effect free: Never mutates any input artifact
    """

    def build(
        self,
        capability: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityReport
        ),
        summary: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySummary
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshot:
        """
        Build an execution capability snapshot from an execution
        capability report and capability summary.

        Args:
            capability: The resolved execution capability report
                for this projection
            summary: The capability summary describing the same
                projection

        Returns:
            An immutable execution capability snapshot

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotError:
                If the capability report and summary do not describe
                the same projection or do not agree on the resolved
                capability
        """

        if summary.projection_name != capability.projection_name:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotError(
                f"Cannot build an execution capability snapshot: summary "
                f"projection name '{summary.projection_name}' does not "
                f"match capability projection name "
                f"'{capability.projection_name}'"
            )

        if summary.capability != capability.capability:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotError(
                f"Cannot build an execution capability snapshot: summary "
                f"capability '{summary.capability}' does not match "
                f"capability report capability '{capability.capability}'"
            )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshot(
            projection_name=capability.projection_name,
            capability=capability.capability,
            reason=capability.reason,
            executable=capability.executable,
            title=summary.title,
            description=summary.description,
        )
