from dataclasses import (
    dataclass,
)

from .research_workspace_action import (
    ResearchWorkspaceAction,
)

from .research_workspace_action_descriptor import (
    ResearchWorkspaceActionDescriptor,
)


@dataclass
class ResearchWorkspaceActionAvailability:
    """
    Represents one action's contextual
    availability, with the reason it is
    unavailable when applicable.
    """

    action: (
        ResearchWorkspaceAction
    )

    available: bool

    reason: (
        str | None
    )

    descriptor: (
        ResearchWorkspaceActionDescriptor
    )

    def to_dict(self):

        return {

            "action":
                self.action.value,

            "available":
                self.available,

            "reason":
                self.reason,

            "descriptor":
                self.descriptor.to_dict(),
        }
