from dataclasses import (
    dataclass,
    field,
)


@dataclass
class ResearchSessionLineageNode:
    """
    Represents one research session
    inside a lineage tree.
    """

    session_id: str

    parent_session_id: (
        str | None
    ) = None

    source_checkpoint_id: (
        str | None
    ) = None

    source_version_id: (
        str | None
    ) = None

    branch_id: (
        str | None
    ) = None

    depth: int = 0

    display_name: (
        str | None
    ) = None

    description: (
        str | None
    ) = None

    status: (
        str | None
    ) = None

    archived: bool = False

    children: list[
        "ResearchSessionLineageNode"
    ] = field(
        default_factory=list,
    )

    def to_dict(self):

        return {

            "session_id":
                self.session_id,

            "parent_session_id":
                self.parent_session_id,

            "source_checkpoint_id":
                self.source_checkpoint_id,

            "source_version_id":
                self.source_version_id,

            "branch_id":
                self.branch_id,

            "depth":
                self.depth,

            "display_name":
                self.display_name,

            "description":
                self.description,

            "status":
                self.status,

            "archived":
                self.archived,

            "children": [

                child.to_dict()

                for child

                in self.children
            ],
        }
