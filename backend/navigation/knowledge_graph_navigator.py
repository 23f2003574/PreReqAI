from backend.models import (
    Paper,
)

from backend.graph import (
    KnowledgeGraphQueryEngine,
)

from .navigation_result import (
    NavigationResult,
)


class KnowledgeGraphNavigator:
    """
    Navigates the Paper Knowledge Graph,
    reusing the existing query engine rather
    than a second, parallel representation.
    """

    def __init__(self):

        self.query_engine = (
            KnowledgeGraphQueryEngine()
        )

    def navigate(

        self,

        paper: Paper,

        query: str,

    ) -> NavigationResult:

        query = query.strip()

        node = self.query_engine.get_node(
            paper.knowledge_graph,
            query,
        )

        if node is None:

            node = next(
                (
                    candidate
                    for candidate in paper.knowledge_graph.nodes
                    if candidate.label.lower()
                    == query.lower()
                ),
                None,
            )

        if node is None:

            raise ValueError(

                f"Knowledge graph node "

                f"'{query}' not found."
            )

        outgoing = (
            self.query_engine.outgoing_neighbors(
                paper.knowledge_graph,
                node.node_id,
            )
        )

        incoming = (
            self.query_engine.incoming_neighbors(
                paper.knowledge_graph,
                node.node_id,
            )
        )

        return NavigationResult(

            target="knowledge_graph",

            title=node.label,

            summary=(
                f"{node.node_type} node with "
                f"{len(outgoing)} outgoing and "
                f"{len(incoming)} incoming "
                "relationship(s)."
            ),

            metadata={

                "node_id":
                    node.node_id,

                "node_type":
                    node.node_type,

                "outgoing_neighbors":
                    outgoing,

                "incoming_neighbors":
                    incoming,
            },
        )
