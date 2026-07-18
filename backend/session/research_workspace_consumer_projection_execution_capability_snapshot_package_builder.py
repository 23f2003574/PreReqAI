from .research_workspace_consumer_projection_execution_capability_descriptor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptor,
)

from .research_workspace_consumer_projection_execution_capability_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshot,
)

from .research_workspace_consumer_projection_execution_capability_snapshot_package import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackage,
)

from .research_workspace_consumer_projection_execution_capability_snapshot_package_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageBuilder:
    """
    Validates and composes an existing execution capability snapshot
    and capability descriptor into one immutable execution
    capability snapshot package.

    The builder's responsibility is validation and composition, not
    recalculation or repair. It does NOT re-run capability
    resolution, recalculate the descriptor, access repositories, or
    derive new policy.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same package
    - Side-effect free: Never mutates any input artifact
    """

    def build(
        self,
        snapshot: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshot
        ),
        descriptor: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptor
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackage:
        """
        Build an execution capability snapshot package from an
        execution capability snapshot and capability descriptor.

        Args:
            snapshot: The execution capability snapshot for this
                projection
            descriptor: The capability descriptor describing the
                same projection

        Returns:
            An immutable execution capability snapshot package

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageError:
                If the snapshot and descriptor do not describe the
                same projection or do not agree on whether the
                projection is executable
        """

        if descriptor.projection_name != snapshot.projection_name:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageError(
                f"Cannot build an execution capability snapshot package: "
                f"descriptor projection name '{descriptor.projection_name}' "
                f"does not match snapshot projection name "
                f"'{snapshot.projection_name}'"
            )

        if descriptor.executable != snapshot.executable:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageError(
                f"Cannot build an execution capability snapshot package: "
                f"descriptor executable flag '{descriptor.executable}' does "
                f"not match snapshot executable flag "
                f"'{snapshot.executable}'"
            )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackage(
            projection_name=snapshot.projection_name,
            capability=snapshot.capability,
            classification=descriptor.classification,
            executable=snapshot.executable,
            title=descriptor.title,
            description=descriptor.description,
        )
