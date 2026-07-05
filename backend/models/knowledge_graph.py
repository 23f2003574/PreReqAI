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

        self.edges.append(edge)
