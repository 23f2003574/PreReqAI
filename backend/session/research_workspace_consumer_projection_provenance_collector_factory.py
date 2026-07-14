from .research_workspace_consumer_projection_provenance_collector import (
    ResearchWorkspaceConsumerProjectionProvenanceCollector,
)


class ResearchWorkspaceConsumerProjectionProvenanceCollectorFactory:
    """
    Application-scoped factory that
    creates a fresh, operation-scoped
    provenance collector for each
    dynamic consumer projection
    operation.
    """

    def create(

        self,

        *,

        operation_name,

    ):

        return (

            ResearchWorkspaceConsumerProjectionProvenanceCollector(

                operation_name=(
                    operation_name
                ),
            )
        )
