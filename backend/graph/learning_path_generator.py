from .knowledge_graph_traversal_engine import (
    KnowledgeGraphTraversalEngine,
)

from backend.models import (
    KnowledgeGraph,
)


class LearningPathGenerator:
    """
    Generates deterministic prerequisite
    learning paths from the Knowledge Graph.
    """

    # Only real prerequisites count: a "co_occurs_with" edge means two concepts share a paragraph, which
    # would otherwise put unrelated concepts (a Transformer's path listing Q-Learning) into the path.
    PATH_RELATIONSHIPS = frozenset({"depends_on"})

    def __init__(self):

        self.traversal = (
            KnowledgeGraphTraversalEngine()
        )

    def generate(
        self,
        graph: KnowledgeGraph,
        concept_name: str,
    ) -> list[str]:

        start_node = f"concept:{concept_name}"

        if not graph.node_exists(start_node):

            return []

        traversal = self.traversal.breadth_first_search(
            graph,
            start_node,
            self.PATH_RELATIONSHIPS,
        )

        return [
            node.replace("concept:", "")
            for node in traversal
        ]
