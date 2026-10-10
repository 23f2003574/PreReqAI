from .research_workspace_consumer_projection_diagnostics_collector import (
    ResearchWorkspaceConsumerProjectionDiagnosticsCollector,
)

from .research_workspace_monotonic_clock import (
    ResearchWorkspaceMonotonicClock,
)


class ResearchWorkspaceConsumerProjectionDiagnosticsFactory:
    """
    Application-scoped factory that
    creates a fresh, operation-scoped
    diagnostics collector for each
    diagnostic consumer projection
    operation.
    """

    def __init__(

        self,

        clock=None,

    ):

        self._clock = (

            clock

            or ResearchWorkspaceMonotonicClock()
        )

    def create(

        self,

        *,

        operation_name,

    ):

        return (

            ResearchWorkspaceConsumerProjectionDiagnosticsCollector(

                operation_name=(
                    operation_name
                ),

                clock=self._clock,
            )
        )
