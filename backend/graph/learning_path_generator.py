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
        )

        return [
            node.replace("concept:", "")
            for node in traversal
        ]
