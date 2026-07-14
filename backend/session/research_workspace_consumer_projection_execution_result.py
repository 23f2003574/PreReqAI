from dataclasses import (
    dataclass,
)

from typing import (
    Optional,
)

from .research_workspace_consumer_projection_diagnostic_report import (
    ResearchWorkspaceConsumerProjectionDiagnosticReport,
)

from .research_workspace_consumer_projection_execution_receipt import (
    ResearchWorkspaceConsumerProjectionExecutionReceipt,
)

from .research_workspace_consumer_projection_fingerprint_snapshot import (
    ResearchWorkspaceConsumerProjectionFingerprintSnapshot,
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

    After Commit #13, the result also
    includes the fingerprint snapshot
    and the immutable execution receipt.
    """

    projection: object

    diagnostics: (
        ResearchWorkspaceConsumerProjectionDiagnosticReport
    )

    provenance: object = None

    fingerprint: (
        Optional[ResearchWorkspaceConsumerProjectionFingerprintSnapshot]
    ) = None

    receipt: (
        Optional[ResearchWorkspaceConsumerProjectionExecutionReceipt]
    ) = None
