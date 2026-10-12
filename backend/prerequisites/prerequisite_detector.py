from backend.models import (
    Paper,
    Prerequisite,
)


class PrerequisiteDetector:
    """
    Identifies prerequisite concepts required
    to understand a research paper.

    The initial implementation uses deterministic
    rules derived from the detected concepts.
    """

    PREREQUISITE_RULES = {

        "Transformer": [
            "Attention",
            "Neural Networks",
        ],

        "Multi-Head Attention": [
            "Attention",
            "Linear Algebra",
        ],

        "Attention": [
            "Linear Algebra",
            "Probability",
        ],

        "Softmax": [
            "Probability",
        ],

        "Graph Neural Network": [
            "Graphs",
            "Neural Networks",
        ],

        "Policy Gradient": [
            "Markov Decision Process",
            "Probability",
            "Calculus",
        ],

        "Self-Attention": [
            "Attention",
            "Linear Algebra",
        ],

        "Diffusion Model": [
            "Probability",
            "Neural Networks",
        ],

        "Forward Process": [
            "Probability",
        ],

        "Noise Schedule": [
            "Probability",
        ],

        "Score Matching": [
            "Probability",
            "Neural Networks",
            "Calculus",
        ],

        "U-Net": [
            "Neural Networks",
        ],

        "Cross-Attention": [
            "Attention",
            "Linear Algebra",
        ],

        "Positional Encoding": [
            "Linear Algebra",
        ],

        "Layer Normalization": [
            "Neural Networks",
            "Probability",
        ],

        "Residual Connection": [
            "Neural Networks",
        ],

        "Feed Forward Network": [
            "Neural Networks",
            "Linear Algebra",
        ],

        "Reverse Process": [
            "Probability",
            "Neural Networks",
            "Calculus",
        ],

        "Markov Decision Process": [
            "Probability",
        ],

        "Bellman Equation": [
            "Markov Decision Process",
            "Probability",
        ],

        "Value Function": [
            "Markov Decision Process",
        ],

        "Q-Learning": [
            "Markov Decision Process",
            "Probability",
        ],

        "Actor-Critic": [
            "Markov Decision Process",
            "Neural Networks",
            "Calculus",
        ],

        "Message Passing": [
            "Graphs",
            "Neural Networks",
        ],

        "Graph Convolution": [
            "Graphs",
            "Linear Algebra",
        ],

        "Graph Attention Network": [
            "Graphs",
            "Attention",
        ],

        "Node Embedding": [
            "Graphs",
            "Linear Algebra",
        ],
    }

    def detect(
        self,
        paper: Paper,
    ) -> Paper:

        paper.prerequisites.clear()

        discovered = set()

        for concept in paper.concepts:

            for prerequisite in self.PREREQUISITE_RULES.get(
                concept.name,
                [],
            ):

                if prerequisite in discovered:
                    continue

                paper.prerequisites.append(

                    Prerequisite(

                        concept=prerequisite,

                        reason=(
                            f"Required to understand "
                            f"{concept.name}"
                        ),

                        confidence=1.0,
                    )
                )

                discovered.add(prerequisite)

        return paper
