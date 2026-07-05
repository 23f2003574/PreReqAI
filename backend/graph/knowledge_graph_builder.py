from backend.models import (
    Paper,
    GraphNode,
)


class KnowledgeGraphBuilder:
    """
    Initializes the Paper Knowledge Graph
    using the extracted structural objects.

    Relationships will be added in future
    commits.
    """

    def build(
        self,
        paper: Paper,
    ) -> Paper:

        paper.knowledge_graph.nodes.clear()

        for concept in paper.concepts:

            paper.knowledge_graph.add_node(

                GraphNode(
                    node_id=f"concept:{concept.name}",
                    node_type="concept",
                    label=concept.name,
                )
            )

        for equation in paper.equations:

            paper.knowledge_graph.add_node(

                GraphNode(
                    node_id=f"equation:{equation.equation_id}",
                    node_type="equation",
                    label=equation.expression,
                )
            )

        for algorithm in paper.algorithms:

            paper.knowledge_graph.add_node(

                GraphNode(
                    node_id=f"algorithm:{algorithm.algorithm_id}",
                    node_type="algorithm",
                    label=algorithm.title,
                )
            )

        return paper
