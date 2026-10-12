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

        "Transformer": [
            "Attention",
            "Multi-Head Attention",
            "Positional Encoding",
            "Layer Normalization",
            "Residual Connection",
            "Feed Forward Network",
        ],

        "Multi-Head Attention": [
            "Attention",
            "Self-Attention",
        ],

        "Self-Attention": [
            "Attention",
        ],

        "Cross-Attention": [
            "Attention",
        ],

        "Attention": [
            "Softmax",
        ],

        "Graph Neural Network": [
            "Message Passing",
        ],

        "Graph Attention Network": [
            "Attention",
            "Graph Neural Network",
            "Message Passing",
        ],

        "Graph Convolution": [
            "Graph Neural Network",
            "Message Passing",
        ],

        "Policy Gradient": [
            "Markov Decision Process",
        ],

        "Backpropagation": [
            "Gradient Descent",
        ],

        "Value Function": [
            "Markov Decision Process",
        ],

        "Bellman Equation": [
            "Value Function",
            "Markov Decision Process",
        ],

        "Q-Learning": [
            "Bellman Equation",
            "Value Function",
            "Markov Decision Process",
        ],

        "Actor-Critic": [
            "Policy Gradient",
            "Value Function",
        ],

        "Diffusion Model": [
            "Forward Process",
            "Reverse Process",
            "Noise Schedule",
        ],

        "Reverse Process": [
            "Forward Process",
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
