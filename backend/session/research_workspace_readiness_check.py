from dataclasses import (
    dataclass,
)

from .research_workspace_capability import (
    ResearchWorkspaceCapability,
)

from .research_workspace_readiness_check_status import (
    ResearchWorkspaceReadinessCheckStatus,
)


@dataclass
class ResearchWorkspaceReadinessCheck:
    """
    Represents one evaluated workspace
    readiness condition.
    """

    name: str

    status: (
        ResearchWorkspaceReadinessCheckStatus
    )

    critical: bool

    message: str

    capability: (
        ResearchWorkspaceCapability | None
    ) = None

    def to_dict(self):

        return {

            "name":
                self.name,

            "status":
                self.status.value,

            "critical":
                self.critical,

            "message":
                self.message,

            "capability":
                (
                    self.capability.value

                    if self.capability

                    is not None

                    else None
                ),
        }
