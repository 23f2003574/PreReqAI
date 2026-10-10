from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionPlanSource:
    """
    A required source resolved as part of planning
    a consumer projection execution.

    Attributes:
        name: Identifies the source
        expired: Whether the source can no longer be used at all
        stale_usable: Whether the source is out of date but still
            usable (ignored when expired is True)
    """

    name: str

    expired: bool

    stale_usable: bool = False

    def to_dict(self):
        return {
            "name": self.name,
            "expired": self.expired,
            "stale_usable": self.stale_usable,
        }
