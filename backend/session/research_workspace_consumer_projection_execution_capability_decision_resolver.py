from .research_workspace_consumer_projection_execution_capability_classification import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification,
)

from .research_workspace_consumer_projection_execution_capability_decision import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
)

from .research_workspace_consumer_projection_execution_capability_decision_reason import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason,
)

from .research_workspace_consumer_projection_execution_capability_decision_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReport,
)

from .research_workspace_consumer_projection_execution_capability_snapshot_package import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackage,
)


_RESOLUTIONS = {
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.STANDARD: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason.STANDARD_CAPABILITY,
    ),
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.RESTRICTED: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REVIEW,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason.RESTRICTED_CAPABILITY,
    ),
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.UNSUPPORTED: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REJECT,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason.UNSUPPORTED_CAPABILITY,
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionResolver:
    """
    Resolves a consumer projection's execution capability snapshot
    package into a normalized policy decision, using only the
    package it is given.

    Does NOT orchestrate execution, schedule work, process
    approvals, access repositories, or inspect the capability
    snapshot, descriptor, or profile directly.

    The resolver is:
    - Stateless: No instance state
    - Deterministic: Same package always produces the same decision
        report
    - Side-effect free: Never mutates the input package
    """

    def resolve(
        self,
        package: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackage
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReport:
        """
        Resolve a capability snapshot package into an execution
        capability decision report.

        Args:
            package: The capability snapshot package to resolve

        Returns:
            An immutable execution capability decision report
        """

        decision, reason = _RESOLUTIONS[package.classification]

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReport(
            projection_name=package.projection_name,
            decision=decision,
            reason=reason,
            executable=package.executable,
        )
