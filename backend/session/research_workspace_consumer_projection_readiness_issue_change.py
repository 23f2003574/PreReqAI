from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReadinessIssueChange:
    """
    Presence of one readiness issue code across a previous and a
    current readiness report.

    Attributes:
        code: The issue code this change describes
        previous: Whether the code was present in the previous report
        current: Whether the code was present in the current report
    """

    code: str

    previous: bool

    current: bool

    @property
    def appeared(self) -> bool:
        return (
            not self.previous
            and self.current
        )

    @property
    def resolved(self) -> bool:
        return (
            self.previous
            and not self.current
        )

    @property
    def persistent(self) -> bool:
        return (
            self.previous
            and self.current
        )

    def to_dict(self):
        return {
            "code": self.code,
            "previous": self.previous,
            "current": self.current,
            "appeared": self.appeared,
            "resolved": self.resolved,
            "persistent": self.persistent,
        }
