from .research_workspace_consumer_projection_execution_capability_decision_package import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
)

from .research_workspace_consumer_projection_execution_capability_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshot,
)

from .research_workspace_consumer_projection_execution_capability_registry_snapshot_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotBuilder:
    """
    Builds an immutable snapshot of the complete state of a
    consumer projection execution capability registry.

    The builder's responsibility is validation and composition, not
    recalculation. It does NOT re-run decision resolution,
    recompute packages, or mutate the registry.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same registry state always produces the same
      snapshot
    - Side-effect free: Never mutates the registry or its packages
    """

    def build(

        self,

        registry,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshot:
        """
        Build a registry snapshot from a consumer projection
        execution capability registry.

        Args:
            registry: The registry to snapshot

        Returns:
            An immutable registry snapshot containing every
            registered decision package, sorted by projection_name

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotError:
                If the registry is None or a stored entry is not a
                valid execution capability decision package
        """

        if registry is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotError(
                    "Cannot build a registry snapshot from a "
                    "None registry."
                )
            )

        if not isinstance(

            registry,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotError(
                    "Cannot build a registry snapshot: registry "
                    "must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry."
                )
            )

        packages = []

        for projection_name in registry.list_projection_names():

            package = registry.get(
                projection_name
            )

            if not isinstance(

                package,

                ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotError(
                        "Cannot build a registry snapshot: "
                        f"projection '{projection_name}' is not a "
                        "valid execution capability decision "
                        "package."
                    )
                )

            packages.append(
                package
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshot(
                packages=tuple(
                    packages
                ),
            )
        )
