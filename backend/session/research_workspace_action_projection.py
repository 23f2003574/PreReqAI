from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_action_availability import (
    ResearchWorkspaceActionAvailability,
)

from .research_workspace_action_scope import (
    ResearchWorkspaceActionScope,
)


@dataclass
class ResearchWorkspaceActionProjection:
    """
    Aggregates contextual action
    availability for one scope.
    """

    scope: (
        ResearchWorkspaceActionScope
    )

    entity_id: (
        str | None
    )

    actions: list[
        ResearchWorkspaceActionAvailability
    ] = field(
        default_factory=list,
    )

    available_count: int = 0

    unavailable_count: int = 0

    def to_dict(self):

        return {

            "scope":
                self.scope.value,

            "entity_id":
                self.entity_id,

            "available_count":
                self.available_count,

            "unavailable_count":
                self.unavailable_count,

            "actions": [

                action.to_dict()

                for action

                in self.actions
            ],
        }
