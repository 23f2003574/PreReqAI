from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReadinessIssue:
    """
    One generic problem detected while evaluating
    the readiness of a planned projection execution.

    Attributes:
        code: A generic, stable identifier for the problem
        message: A human-readable description of the problem
    """

    code: str

    message: str

    def to_dict(self):
        return {
            "code": self.code,
            "message": self.message,
        }
