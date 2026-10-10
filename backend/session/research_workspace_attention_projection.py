from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_attention_item import (
    ResearchWorkspaceAttentionItem,
)


@dataclass
class ResearchWorkspaceAttentionProjection:
    """
    Aggregates actionable workspace
    attention items into one consumer-
    facing, priority-ordered result.
    """

    items: list[
        ResearchWorkspaceAttentionItem
    ] = field(
        default_factory=list,
    )

    total_count: int = 0

    actionable_count: int = 0

    critical_count: int = 0

    high_count: int = 0

    def to_dict(self):

        return {

            "total_count":
                self.total_count,

            "actionable_count":
                self.actionable_count,

            "critical_count":
                self.critical_count,

            "high_count":
                self.high_count,

            "items": [

                item.to_dict()

                for item

                in self.items
            ],
        }
