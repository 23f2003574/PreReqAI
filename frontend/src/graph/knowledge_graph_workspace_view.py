from .graph_view_edge import (
    GraphViewEdge,
)

from .graph_view_node import (
    GraphViewNode,
)

from .knowledge_graph_view_model import (
    KnowledgeGraphViewModel,
)


class KnowledgeGraphWorkspaceView:
    """
    Transforms research knowledge graphs
    into interactive workspace view models.
    """

    def __init__(self):

        self.view_model = (
            KnowledgeGraphViewModel()
        )

    def build(

        self,

        knowledge_graph,

    ) -> KnowledgeGraphViewModel:

        nodes = [

            GraphViewNode(

                id=node.node_id,

                label=node.label,

                node_type=node.node_type,

                description=getattr(

                    node,

                    "description",

                    "",
                ),

                source=node,
            )

            for node in knowledge_graph.nodes
        ]

        edges = []

        seen_edges = set()

        for edge in knowledge_graph.edges:

            edge_key = tuple(

                sorted(

                    (
                        edge.source,

                        edge.target,
                    )
                )
            )

            if edge_key in seen_edges:

                continue

            seen_edges.add(
                edge_key
            )

            edges.append(

                GraphViewEdge(

                    source_id=edge.source,

                    target_id=edge.target,

                    relationship=(
                        edge.relationship
                    ),
                )
            )

        self.view_model = (

            KnowledgeGraphViewModel(

                nodes=nodes,

                edges=edges,
            )
        )

        return self.view_model

    def select_node(

        self,

        node_id: str,

    ):

        selected = None

        for node in self.view_model.nodes:

            node.selected = (

                node.id == node_id
            )

            if node.selected:

                selected = node

        self.view_model.selected_node_id = (

            node_id

            if selected

            else None
        )

        return selected
