from dataclasses import (
    dataclass,
)

from typing import (
    Optional,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionDiagnosticsSummary:
    """
    Compact summary of execution diagnostics.

    Summarizes:
    - How much work occurred?
    - Did any stage degrade?
    - Was request-scoped reuse observed?
    - How long did execution take?

    Derived from the finalized diagnostics report,
    not from separate receipt counters during execution.

    Attributes:
        stage_count: Total number of stages executed
        degraded_stage_count: Number of stages with degraded status
        reused_resolution_count: Number of request-scoped input reuses
        total_duration_ms: Total execution duration in milliseconds
    """

    stage_count: int

    degraded_stage_count: int

    reused_resolution_count: int

    total_duration_ms: (
        Optional[float]
    ) = None
