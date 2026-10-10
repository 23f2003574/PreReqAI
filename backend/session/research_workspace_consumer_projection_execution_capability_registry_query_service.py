from .research_workspace_consumer_projection_execution_capability_registry_query_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryQueryError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryQueryService:
    """
    Read-only query interface over a consumer projection execution
    capability registry, separating lookup operations from registry
    storage.

    The service does not own the registry and never mutates it,
    replaces entries, creates packages, or recomputes decisions - it
    only performs lookups against the registry it was given.

    The service is:
    - Stateless: Holds only a reference to the registry it queries
    - Read-only: Never mutates the registry
    - Deterministic: Same registry state always produces the same
      answers
    - Side-effect free: Queries never change registry state
    """

    def __init__(

        self,

        registry,

    ):

        self._registry = registry

    def get(

        self,

        projection_name,

    ):

        if not self._registry.contains(
            projection_name
        ):

            return None

        return self._registry.get(
            projection_name
        )

    def require(

        self,

        projection_name,

    ):

        if not self._registry.contains(
            projection_name
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryQueryError(
                    "Unknown projection: "
                    f"{projection_name}"
                )
            )

        return self._registry.get(
            projection_name
        )

    def exists(

        self,

        projection_name,

    ):

        return self._registry.contains(
            projection_name
        )

    def list_packages(self):

        return tuple(

            self._registry.get(
                projection_name
            )

            for projection_name

            in self._registry.list_projection_names()
        )
