from .research_workspace_consumer_projection_execution_capability import (
    ResearchWorkspaceConsumerProjectionExecutionCapability,
)

from .research_workspace_consumer_projection_execution_capability_package import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityPackage,
)

from .research_workspace_consumer_projection_execution_capability_profile import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityProfile,
)


_PROFILES = {
    ResearchWorkspaceConsumerProjectionExecutionCapability.CAPABLE: (
        "EXECUTION_READY"
    ),
    ResearchWorkspaceConsumerProjectionExecutionCapability.LIMITED: (
        "APPROVAL_REQUIRED"
    ),
    ResearchWorkspaceConsumerProjectionExecutionCapability.INCAPABLE: (
        "EXECUTION_BLOCKED"
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionCapabilityProfileBuilder:
    """
    Builds a normalized capability profile from an existing
    execution capability package.

    Owns only classification mapping - it does NOT re-run capability
    resolution, evaluate policy, access repositories, or inspect any
    earlier pipeline stage.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same package always produces the same profile
    - Side-effect free: Never mutates the input package
    """

    def build(
        self,
        package: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityPackage
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityProfile:
        """
        Build a capability profile from an execution capability
        package.

        Args:
            package: The execution capability package to classify

        Returns:
            An immutable, normalized capability profile
        """

        profile = _PROFILES[package.capability]

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityProfile(
            projection_name=package.projection_name,
            capability=package.capability,
            executable=package.executable,
            profile=profile,
        )
