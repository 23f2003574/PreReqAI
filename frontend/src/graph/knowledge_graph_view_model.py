from dataclasses import (
    dataclass,
    field,
)

from .graph_view_edge import (
    GraphViewEdge,
)

from .graph_view_node import (
    GraphViewNode,
)


@dataclass
class KnowledgeGraphViewModel:
    """
    Represents the complete visual
    knowledge graph state.
    """

    nodes: list[
        GraphViewNode
    ] = field(
        default_factory=list,
    )

    edges: list[
        GraphViewEdge
    ] = field(
        default_factory=list,
    )

    selected_node_id: str | None = None
