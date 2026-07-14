from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_diagnostic_failure import (
    ResearchWorkspaceConsumerProjectionDiagnosticFailure,
)

from .research_workspace_consumer_projection_diagnostic_status import (
    ResearchWorkspaceConsumerProjectionDiagnosticStatus,
)

from .research_workspace_consumer_projection_freshness_evaluation import (
    ResearchWorkspaceConsumerProjectionFreshnessEvaluation,
)


@dataclass
class ResearchWorkspaceConsumerProjectionInputDiagnostic:
    """
    Aggregates how one request-scoped
    shared input was resolved and reused
    during one projection operation.
    """

    name: str

    key: (
        str | None
    )

    resolution_count: int

    reuse_count: int

    duration_ms: float

    status: (
        ResearchWorkspaceConsumerProjectionDiagnosticStatus
    )

    failure: (
        ResearchWorkspaceConsumerProjectionDiagnosticFailure
        | None
    )

    freshness: (
        ResearchWorkspaceConsumerProjectionFreshnessEvaluation
        | None
    ) = None

    def to_dict(self):

        return {

            "name":
                self.name,

            "key":
                self.key,

            "resolution_count":
                self.resolution_count,

            "reuse_count":
                self.reuse_count,

            "duration_ms":
                self.duration_ms,

            "status":
                self.status.value,

            "failure": (

                self.failure.to_dict()

                if self.failure

                is not None

                else None
            ),

            "freshness": (

                self.freshness.to_dict()

                if self.freshness

                is not None

                else None
            ),
        }
