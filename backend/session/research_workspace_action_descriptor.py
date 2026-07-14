from dataclasses import (
    dataclass,
)

from .research_workspace_action import (
    ResearchWorkspaceAction,
)

from .research_workspace_action_scope import (
    ResearchWorkspaceActionScope,
)

from .research_workspace_capability import (
    ResearchWorkspaceCapability,
)


@dataclass
class ResearchWorkspaceActionDescriptor:
    """
    Describes one known workspace action's
    stable, consumer-facing metadata.
    """

    action: (
        ResearchWorkspaceAction
    )

    scope: (
        ResearchWorkspaceActionScope
    )

    label: str

    description: str

    capability: (
        ResearchWorkspaceCapability | None
    )

    mutating: bool

    destructive: bool

    def to_dict(self):

        return {

            "action":
                self.action.value,

            "scope":
                self.scope.value,

            "label":
                self.label,

            "description":
                self.description,

            "capability": (

                self.capability.value

                if self.capability

                is not None

                else None
            ),

            "mutating":
                self.mutating,

            "destructive":
                self.destructive,
        }
