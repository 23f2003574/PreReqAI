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
class ResearchWorkspaceConsumerProjectionHealthSignalChange:
    """
    Severity change of one quality signal code between a previous
    and a current quality signal report.

    A `None` severity means the signal code was absent from that
    report - not a stored full signal object.

    Attributes:
        code: The quality signal code this change describes
        previous_severity: Severity in the previous report, or None if absent
        current_severity: Severity in the current report, or None if absent
    """

    code: (
        ResearchWorkspaceConsumerProjectionQualitySignalCode
    )

    previous_severity: (
        Optional[
            ResearchWorkspaceConsumerProjectionQualitySignalSeverity
        ]
    )

    current_severity: (
        Optional[
            ResearchWorkspaceConsumerProjectionQualitySignalSeverity
        ]
    )

    @property
    def appeared(self) -> bool:
        return (
            self.previous_severity is None
            and self.current_severity is not None
        )

    @property
    def resolved(self) -> bool:
        return (
            self.previous_severity is not None
            and self.current_severity is None
        )

    @property
    def severity_changed(self) -> bool:
        return (
            self.previous_severity is not None
            and self.current_severity is not None
            and self.previous_severity != self.current_severity
        )
