from dataclasses import (
    dataclass,
)

from .research_workspace_change_event import (
    ResearchWorkspaceChangeEvent,
)


@dataclass
class ResearchWorkspaceChangePage:
    """
    Represents one cursor-based page of
    workspace change events.
    """

    events: list[
        ResearchWorkspaceChangeEvent
    ]

    next_cursor: (
        int | None
    )

    has_more: bool

    def to_dict(self):

        return {

            "events": [

                event.to_dict()

                for event

                in self.events
            ],

            "next_cursor":
                self.next_cursor,

            "has_more":
                self.has_more,
        }
