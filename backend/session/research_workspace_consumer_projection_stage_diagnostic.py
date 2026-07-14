from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_diagnostic_failure import (
    ResearchWorkspaceConsumerProjectionDiagnosticFailure,
)

from .research_workspace_consumer_projection_diagnostic_stage_kind import (
    ResearchWorkspaceConsumerProjectionDiagnosticStageKind,
)

from .research_workspace_consumer_projection_diagnostic_status import (
    ResearchWorkspaceConsumerProjectionDiagnosticStatus,
)


@dataclass
class ResearchWorkspaceConsumerProjectionStageDiagnostic:
    """
    Records how one meaningful unit of
    projection execution behaved.
    """

    name: str

    kind: (
        ResearchWorkspaceConsumerProjectionDiagnosticStageKind
    )

    status: (
        ResearchWorkspaceConsumerProjectionDiagnosticStatus
    )

    duration_ms: float

    reason_code: (
        str | None
    )

    failure: (
        ResearchWorkspaceConsumerProjectionDiagnosticFailure
        | None
    )

    def to_dict(self):

        return {

            "name":
                self.name,

            "kind":
                self.kind.value,

            "status":
                self.status.value,

            "duration_ms":
                self.duration_ms,

            "reason_code":
                self.reason_code,

            "failure": (

                self.failure.to_dict()

                if self.failure

                is not None

                else None
            ),
        }
