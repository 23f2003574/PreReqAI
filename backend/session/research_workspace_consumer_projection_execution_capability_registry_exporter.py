from .research_workspace_consumer_projection_execution_capability_decision_package import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
)

from .research_workspace_consumer_projection_execution_capability_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_export import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExport,
)

from .research_workspace_consumer_projection_execution_capability_registry_export_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExportError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter:
    """
    Converts a consumer projection execution capability registry
    into a portable, immutable export representation for downstream
    integrations.

    The exporter's responsibility is transformation, not
    recalculation. It does NOT re-run decision resolution, replace
    packages, or derive any metadata beyond the projection count.

    The exporter is:
    - Stateless: No instance state
    - Deterministic: Same registry state always produces the same
      export
    - Side-effect free: Never mutates the registry or its packages
    """

    def export(

        self,

        registry,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExport:
        """
        Export a consumer projection execution capability registry.

        Args:
            registry: The registry to export

        Returns:
            An immutable registry export containing every
            registered decision package, sorted by projection_name,
            and the total projection count

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExportError:
                If the registry is None or a stored entry is not a
                valid execution capability decision package
        """

        if registry is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExportError(
                    "Cannot export a None registry."
                )
            )

        if not isinstance(

            registry,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExportError(
                    "Cannot export registry: registry must be a "
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
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExportError(
                        "Cannot export registry: projection "
                        f"'{projection_name}' is not a valid "
                        "execution capability decision package."
                    )
                )

            packages.append(
                package
            )

        packages = tuple(
            packages
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExport(
                packages=packages,

                total_projections=len(
                    packages
                ),
            )
        )
