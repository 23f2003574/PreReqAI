from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_quality_signal import (
    ResearchWorkspaceConsumerProjectionQualitySignal,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionQualitySignalReport:
    """
    Compact, deterministic report of the quality signals present
    on one finalized execution receipt.

    An execution with no notable conditions produces an empty
    `signals` tuple and both flags false - that already means "no
    configured quality concerns detected," so no synthetic
    "healthy" signal is invented to avoid an empty list.

    This report is not a scoring system. It does not rank, weight,
    or aggregate signals into a single health value.

    Attributes:
        execution_id: Execution ID of the receipt this report describes
        projection_name: Name of the projection that was executed
        signals: Stable-ordered tuple of detected quality signals
        has_warnings: True if any signal has WARNING severity
        has_critical_signals: True if any signal has CRITICAL severity
    """

    execution_id: str

    projection_name: str

    signals: tuple[
        ResearchWorkspaceConsumerProjectionQualitySignal,
        ...,
    ]

    has_warnings: bool

    has_critical_signals: bool

    @property
    def signal_count(self) -> int:
        return len(self.signals)

    def to_dict(self):
        """
        Serialize the report to a deterministic dictionary.
        """

        return {
            "execution_id": self.execution_id,
            "projection_name": self.projection_name,
            "signals": [
                {
                    "code": signal.code.value,
                    "severity": signal.severity.value,
                    "message": signal.message,
                    "value": signal.value,
                }
                for signal in self.signals
            ],
            "has_warnings": self.has_warnings,
            "has_critical_signals": self.has_critical_signals,
        }
