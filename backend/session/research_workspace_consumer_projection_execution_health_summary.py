from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_health import (
    ResearchWorkspaceConsumerProjectionExecutionHealth,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionHealthSummary:
    """
    Compact, deterministic execution-level health assessment
    reduced from a quality signal report.

    This is not a numeric score - it is a stable three-value
    classification (see ResearchWorkspaceConsumerProjectionExecutionHealth)
    plus the signal counts it was derived from.

    Attributes:
        execution_id: Execution ID reused from the quality signal report
        projection_name: Projection name reused from the quality signal report
        health: Overall health classification
        signal_count: Total number of quality signals
        warning_count: Number of WARNING-severity signals
        critical_count: Number of CRITICAL-severity signals
    """

    execution_id: str

    projection_name: str

    health: (
        ResearchWorkspaceConsumerProjectionExecutionHealth
    )

    signal_count: int

    warning_count: int

    critical_count: int

    @property
    def has_concerns(self) -> bool:
        return (
            self.health
            != ResearchWorkspaceConsumerProjectionExecutionHealth.HEALTHY
        )

    def to_dict(self):
        """
        Serialize the health summary to a deterministic dictionary.
        """

        return {
            "execution_id": self.execution_id,
            "projection_name": self.projection_name,
            "health": self.health.value,
            "signal_count": self.signal_count,
            "warning_count": self.warning_count,
            "critical_count": self.critical_count,
            "has_concerns": self.has_concerns,
        }
