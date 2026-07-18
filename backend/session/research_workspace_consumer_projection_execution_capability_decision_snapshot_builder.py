from .research_workspace_consumer_projection_execution_capability_decision_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReport,
)

from .research_workspace_consumer_projection_execution_capability_decision_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshot,
)

from .research_workspace_consumer_projection_execution_capability_decision_snapshot_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotError,
)

from .research_workspace_consumer_projection_execution_capability_decision_summary import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummary,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotBuilder:
    """
    Validates and composes an existing execution capability decision
    report and decision summary into one immutable execution
    capability decision snapshot.

    The builder's responsibility is validation and composition, not
    recalculation or repair. It does NOT re-run decision resolution,
    recalculate the summary, access repositories, or derive new
    policy.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same snapshot
    - Side-effect free: Never mutates any input artifact
    """

    def build(
        self,
        decision: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReport
        ),
        summary: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummary
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshot:
        """
        Build an execution capability decision snapshot from an
        execution capability decision report and decision summary.

        Args:
            decision: The resolved execution capability decision
                report for this projection
            summary: The decision summary describing the same
                projection

        Returns:
            An immutable execution capability decision snapshot

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotError:
                If the decision report and summary do not describe
                the same projection or do not agree on the resolved
                decision and reason
        """

        if summary.projection_name != decision.projection_name:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotError(
                f"Cannot build an execution capability decision snapshot: "
                f"summary projection name '{summary.projection_name}' does "
                f"not match decision projection name "
                f"'{decision.projection_name}'"
            )

        if summary.decision != decision.decision:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotError(
                f"Cannot build an execution capability decision snapshot: "
                f"summary decision '{summary.decision}' does not match "
                f"decision report decision '{decision.decision}'"
            )

        if summary.reason != decision.reason:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotError(
                f"Cannot build an execution capability decision snapshot: "
                f"summary reason '{summary.reason}' does not match "
                f"decision report reason '{decision.reason}'"
            )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshot(
            projection_name=decision.projection_name,
            decision=decision.decision,
            reason=decision.reason,
            executable=decision.executable,
            title=summary.title,
            description=summary.description,
        )
