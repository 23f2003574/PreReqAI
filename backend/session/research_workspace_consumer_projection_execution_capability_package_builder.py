from .research_workspace_consumer_projection_execution_capability_package import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityPackage,
)

from .research_workspace_consumer_projection_execution_capability_package_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageError,
)

from .research_workspace_consumer_projection_execution_capability_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshot,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageBuilder:
    """
    Builds a portable execution capability package from an existing
    execution capability snapshot.

    The builder's responsibility is validation and composition, not
    recalculation or repair. It does NOT re-run any policy
    resolution, write logs, publish events, or access repositories.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same snapshot always produces the same package
    - Side-effect free: Never mutates the input snapshot
    """

    def build(
        self,
        snapshot: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshot
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityPackage:
        """
        Build an execution capability package from an execution
        capability snapshot.

        Args:
            snapshot: The execution capability snapshot to compose
                into a package

        Returns:
            An immutable execution capability package

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageError:
                If the snapshot's projection name is empty
        """

        if not snapshot.projection_name:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageError(
                "Cannot build an execution capability package: "
                "projection name must be non-empty"
            )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityPackage(
            projection_name=snapshot.projection_name,
            capability=snapshot.capability,
            executable=snapshot.executable,
            title=snapshot.title,
            description=snapshot.description,
        )
