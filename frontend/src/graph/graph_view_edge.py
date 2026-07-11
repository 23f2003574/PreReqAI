from dataclasses import (
    dataclass,
    field,
)


@dataclass
class GraphViewEdge:
    """
    Represents one visual relationship
    between two knowledge graph nodes.
    """

    source_id: str

    target_id: str

    relationship: str

    metadata: dict = field(
        default_factory=dict,
    )
