from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_attention_item import (
    ResearchWorkspaceAttentionItem,
)


@dataclass
class ResearchWorkspaceAttentionSummary:
    """
    Compact, bootstrap-friendly preview
    of the full attention projection.
    """

    total_count: int = 0

    actionable_count: int = 0

    critical_count: int = 0

    high_count: int = 0

    top_items: list[
        ResearchWorkspaceAttentionItem
    ] = field(
        default_factory=list,
    )

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

            "top_items": [

                item.to_dict()

                for item

                in self.top_items
            ],
        }
