from backend.models import (
    Paper,
    GraphEdge,
)


class ConceptRelationshipBuilder:
    """
    Builds deterministic relationships between
    known concepts using the Concept Registry.

    This forms the initial backbone of the
    Knowledge Graph before AI-assisted reasoning
    is introduced.
    """

    RELATIONSHIPS = {

        "Multi-Head Attention": [
            "Attention",
            "Self-Attention",
        ],

        "Self-Attention": [
            "Attention",
        ],

        "Attention": [
            "Softmax",
        ],

        "Graph Attention Network": [
            "Attention",
            "Graph Neural Network",
        ],

        "Policy Gradient": [
            "Markov Decision Process",
        ],

        "Bellman Equation": [
            "Value Function",
        ],

        "Graph Convolution": [
            "Graph Neural Network",
        ],
    }

    def build(
        self,
        paper: Paper,
    ) -> Paper:

        existing = {
            concept.name
            for concept in paper.concepts
        }

        for concept_name, dependencies in self.RELATIONSHIPS.items():

            if concept_name not in existing:
                continue

            for dependency in dependencies:

                if dependency not in existing:
                    continue

                paper.knowledge_graph.add_edge(

                    GraphEdge(
                        source=f"concept:{concept_name}",
                        target=f"concept:{dependency}",
                        relationship="depends_on",
                    )
                )

        return paper
