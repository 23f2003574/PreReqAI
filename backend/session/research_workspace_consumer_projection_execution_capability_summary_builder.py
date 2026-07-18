from .research_workspace_consumer_projection_execution_capability import (
    ResearchWorkspaceConsumerProjectionExecutionCapability,
)

from .research_workspace_consumer_projection_execution_capability_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReport,
)

from .research_workspace_consumer_projection_execution_capability_summary import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySummary,
)


_PRESENTATIONS = {
    ResearchWorkspaceConsumerProjectionExecutionCapability.CAPABLE: (
        "Execution Capable",
        "Projection is capable of execution.",
    ),
    ResearchWorkspaceConsumerProjectionExecutionCapability.LIMITED: (
        "Limited Execution",
        "Projection requires additional approval before execution.",
    ),
    ResearchWorkspaceConsumerProjectionExecutionCapability.INCAPABLE: (
        "Execution Incapable",
        "Projection cannot be executed.",
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionCapabilitySummaryBuilder:
    """
    Builds a compact, presentation-ready summary from a consumer
    projection's execution capability report.

    Owns only presentation mapping - it does NOT re-run capability
    resolution, re-derive the primary reason, access repositories,
    or inspect the execution outcome, verdict, authorization, or any
    earlier report.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same report always produces the same summary
    - Side-effect free: Never mutates the input report
    """

    def build(
        self,
        capability: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityReport
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilitySummary:
        """
        Build a capability summary from an execution capability
        report.

        Args:
            capability: The resolved execution capability report to
                summarize

        Returns:
            An immutable, compact capability summary
        """

        title, description = _PRESENTATIONS[capability.capability]

        return ResearchWorkspaceConsumerProjectionExecutionCapabilitySummary(
            projection_name=capability.projection_name,
            capability=capability.capability,
            reason=capability.reason,
            title=title,
            description=description,
            executable=capability.executable,
        )
