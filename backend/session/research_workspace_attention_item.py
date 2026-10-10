from dataclasses import (
    dataclass,
)

from .research_workspace_attention_category import (
    ResearchWorkspaceAttentionCategory,
)

from .research_workspace_attention_severity import (
    ResearchWorkspaceAttentionSeverity,
)


@dataclass
class ResearchWorkspaceAttentionItem:
    """
    Represents one actionable condition
    derived from existing workspace state.
    """

    attention_id: str

    category: (
        ResearchWorkspaceAttentionCategory
    )

    severity: (
        ResearchWorkspaceAttentionSeverity
    )

    title: str

    message: str

    actionable: bool

    action: (
        str | None
    )

    entity_type: (
        str | None
    )

    entity_id: (
        str | None
    )

    source: str

    def to_dict(self):

        return {

            "attention_id":
                self.attention_id,

            "category":
                self.category.value,

            "severity":
                self.severity.value,

            "title":
                self.title,

            "message":
                self.message,

            "actionable":
                self.actionable,

            "action":
                self.action,

            "entity_type":
                self.entity_type,

            "entity_id":
                self.entity_id,

            "source":
                self.source,
        }
