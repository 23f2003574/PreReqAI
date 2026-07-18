from .research_workspace_consumer_projection_execution_capability_classification import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification,
)

from .research_workspace_consumer_projection_execution_capability_classification_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationReport,
)

from .research_workspace_consumer_projection_execution_capability_descriptor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptor,
)


_PRESENTATIONS = {
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.STANDARD: (
        "Standard Capability",
        "Projection supports normal execution.",
    ),
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.RESTRICTED: (
        "Restricted Capability",
        "Projection requires additional approval before execution.",
    ),
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.UNSUPPORTED: (
        "Unsupported Capability",
        "Projection is not capable of execution.",
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptorBuilder:
    """
    Builds a compact, presentation-ready descriptor from a consumer
    projection's execution capability classification report.

    Owns only presentation mapping - it does NOT re-run
    classification resolution, re-derive the primary reason, access
    repositories, or inspect the capability profile, package,
    snapshot, or any earlier report.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same report always produces the same descriptor
    - Side-effect free: Never mutates the input report
    """

    def build(
        self,
        classification: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationReport
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptor:
        """
        Build a capability descriptor from an execution capability
        classification report.

        Args:
            classification: The resolved execution capability
                classification report to describe

        Returns:
            An immutable, compact capability descriptor
        """

        title, description = _PRESENTATIONS[classification.classification]

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptor(
            projection_name=classification.projection_name,
            classification=classification.classification,
            title=title,
            description=description,
            executable=classification.executable,
        )
