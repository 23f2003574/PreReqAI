from dataclasses import (
    dataclass,
)


@dataclass
class ResearchWorkspaceConsumerProjectionDiagnosticFailure:
    """
    A sanitized, consumer-safe summary of
    a diagnostic failure. Never carries a
    raw traceback or exception message.
    """

    error_type: str

    reason: (
        str | None
    ) = None

    def to_dict(self):

        return {

            "error_type":
                self.error_type,

            "reason":
                self.reason,
        }
