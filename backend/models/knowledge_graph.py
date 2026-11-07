from dataclasses import dataclass, field


@dataclass
class GraphNode:

    node_id: str

    node_type: str

    label: str


@dataclass
class GraphEdge:

    source: str

    target: str

    relationship: str


@dataclass
class KnowledgeGraph:

    nodes: list[GraphNode] = field(default_factory=list)

    edges: list[GraphEdge] = field(default_factory=list)

    def add_node(
        self,
        node: GraphNode,
    ):

        self.nodes.append(node)

    def add_edge(
        self,
        edge: GraphEdge,
    ):

        # A self-loop is a malformed relationship: it would make a concept its own prerequisite.
        if edge.source == edge.target:

            raise ValueError(f"Graph edge cannot connect {edge.source!r} to itself")

        self.edges.append(edge)

    def node_exists(
        self,
        node_id: str,
    ) -> bool:

        return any(
            node.node_id == node_id
            for node in self.nodes
        )
