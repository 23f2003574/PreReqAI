from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_diagnostic_report import (
    ResearchWorkspaceConsumerProjectionDiagnosticReport,
)


@dataclass
class ResearchWorkspaceConsumerProjectionExecutionResult:
    """
    Pairs a normal consumer projection
    with the diagnostic report produced
    while building it. Only used by
    explicit diagnostic gateway
    operations, never by the normal
    consumer contract.
    """

    projection: object

    diagnostics: (
        ResearchWorkspaceConsumerProjectionDiagnosticReport
    )

    provenance: object = None
