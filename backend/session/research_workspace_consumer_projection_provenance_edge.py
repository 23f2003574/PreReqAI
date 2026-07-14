from dataclasses import (
    dataclass,
)


@dataclass
class ResearchWorkspaceConsumerProjectionProvenanceEdge:
    """
    A directed lineage relationship:
    from_node_id contributed directly
    to to_node_id.
    """

    from_node_id: str

    to_node_id: str

    def to_dict(self):

        return {

            "from_node_id":
                self.from_node_id,

            "to_node_id":
                self.to_node_id,
        }
