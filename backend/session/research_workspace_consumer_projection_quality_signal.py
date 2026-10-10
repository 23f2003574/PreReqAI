from dataclasses import (
    dataclass,
)

from typing import (
    Optional,
)

from .research_workspace_consumer_projection_quality_signal_code import (
    ResearchWorkspaceConsumerProjectionQualitySignalCode,
)

from .research_workspace_consumer_projection_quality_signal_severity import (
    ResearchWorkspaceConsumerProjectionQualitySignalSeverity,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionQualitySignal:
    """
    One notable, explicit execution condition extracted from a
    finalized execution receipt.

    A signal is a compact fact, not a diagnosis - it does not embed
    the full receipt, diagnostics report, freshness records, or
    provenance graph.

    Attributes:
        code: Which condition this signal identifies
        severity: Deterministic severity of the condition
        message: Human-readable description of the condition
        value: Optional compact numeric value (e.g. an affected count)
    """

    code: (
        ResearchWorkspaceConsumerProjectionQualitySignalCode
    )

    severity: (
        ResearchWorkspaceConsumerProjectionQualitySignalSeverity
    )

    message: str

    value: (
        Optional[int]
    ) = None
