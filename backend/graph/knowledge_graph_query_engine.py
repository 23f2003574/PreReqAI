from backend.models import (
    GraphNode,
    KnowledgeGraph,
)


class KnowledgeGraphQueryEngine:
    """
    Provides reusable query operations over
    the Knowledge Graph.
    """

    def get_node(
        self,
        graph: KnowledgeGraph,
        node_id: str,
    ) -> GraphNode | None:

        for node in graph.nodes:

            if node.node_id == node_id:
                return node

        return None

    def find_by_type(
        self,
        graph: KnowledgeGraph,
        node_type: str,
    ) -> list[GraphNode]:

        return [

            node

            for node in graph.nodes

            if node.node_type == node_type
        ]

    def outgoing_neighbors(
        self,
        graph: KnowledgeGraph,
        node_id: str,
    ) -> list[str]:

        return [

            edge.target

            for edge in graph.edges

            if edge.source == node_id
        ]

    def incoming_neighbors(
        self,
        graph: KnowledgeGraph,
        node_id: str,
    ) -> list[str]:

        return [

            edge.source

            for edge in graph.edges

            if edge.target == node_id
        ]
