from .research_workspace_consumer_projection_execution_capability_classification import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification,
)

from .research_workspace_consumer_projection_execution_capability_classification_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationReport,
)

from .research_workspace_consumer_projection_execution_capability_profile import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityProfile,
)


_CLASSIFICATIONS = {
    "EXECUTION_READY": (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.STANDARD
    ),
    "APPROVAL_REQUIRED": (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.RESTRICTED
    ),
    "EXECUTION_BLOCKED": (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.UNSUPPORTED
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationResolver:
    """
    Resolves a consumer projection's execution capability profile
    into a standardized domain classification, using only the
    capability profile it is given.

    Does NOT orchestrate execution, schedule work, process
    approvals, access repositories, or inspect the capability
    package, snapshot, or any earlier report directly.

    The resolver is:
    - Stateless: No instance state
    - Deterministic: Same profile always produces the same
        classification report
    - Side-effect free: Never mutates the input profile
    """

    def resolve(
        self,
        profile: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityProfile
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationReport:
        """
        Resolve a capability profile into an execution capability
        classification report.

        Args:
            profile: The capability profile to classify

        Returns:
            An immutable execution capability classification report
        """

        classification = _CLASSIFICATIONS[profile.profile]

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationReport(
            projection_name=profile.projection_name,
            classification=classification,
            profile=profile.profile,
            executable=profile.executable,
        )
