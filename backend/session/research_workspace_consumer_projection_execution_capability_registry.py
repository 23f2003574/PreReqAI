from .research_workspace_consumer_projection_execution_capability_registry_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry:
    """
    In-memory registry of finalized consumer projection execution
    capability decision packages, keyed by projection name.

    Performs no policy evaluation and never modifies a stored
    package - it is strictly a deterministic lookup component
    that consumers use instead of rebuilding the decision pipeline.
    """

    def __init__(self):

        self._packages = {}

    def register(

        self,

        package,

    ):

        projection_name = (
            package.projection_name
        )

        if not projection_name:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryError(
                    "projection_name must not be empty."
                )
            )

        self._packages[
            projection_name
        ] = package

    def get(

        self,

        projection_name,

    ):

        if projection_name not in self._packages:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryError(
                    "Unknown projection: "
                    f"{projection_name}"
                )
            )

        return self._packages[
            projection_name
        ]

    def contains(

        self,

        projection_name,

    ):

        return (
            projection_name
            in self._packages
        )

    def list_projection_names(self):

        return tuple(
            sorted(
                self._packages
                .keys()
            )
        )
