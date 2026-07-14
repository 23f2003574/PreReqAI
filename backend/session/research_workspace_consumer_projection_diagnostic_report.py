from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_consumer_projection_diagnostic_status import (
    ResearchWorkspaceConsumerProjectionDiagnosticStatus,
)

from .research_workspace_consumer_projection_input_diagnostic import (
    ResearchWorkspaceConsumerProjectionInputDiagnostic,
)

from .research_workspace_consumer_projection_stage_diagnostic import (
    ResearchWorkspaceConsumerProjectionStageDiagnostic,
)


@dataclass
class ResearchWorkspaceConsumerProjectionDiagnosticReport:
    """
    The immutable, finalized diagnostic
    record for one logical consumer
    projection operation.
    """

    operation_name: str

    status: (
        ResearchWorkspaceConsumerProjectionDiagnosticStatus
    )

    duration_ms: float

    inputs: list[
        ResearchWorkspaceConsumerProjectionInputDiagnostic
    ] = field(
        default_factory=list,
    )

    stages: list[
        ResearchWorkspaceConsumerProjectionStageDiagnostic
    ] = field(
        default_factory=list,
    )

    def to_dict(self):

        return {

            "operation_name":
                self.operation_name,

            "status":
                self.status.value,

            "duration_ms":
                self.duration_ms,

            "inputs": [

                input_diagnostic.to_dict()

                for input_diagnostic

                in self.inputs
            ],

            "stages": [

                stage.to_dict()

                for stage

                in self.stages
            ],
        }
