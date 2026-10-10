from dataclasses import dataclass


@dataclass(frozen=True)
class Concept:

    name: str
    domain: str


class ConceptRegistry:
    """
    Central registry of concepts currently
    supported by PreReqAI.

    This registry acts as the foundation for
    future concept extraction pipelines.
    """

    def __init__(self):

        self._concepts = [

            # Transformers

            Concept("Transformer", "transformers"),
            Concept("Attention", "transformers"),
            Concept("Self-Attention", "transformers"),
            Concept("Cross-Attention", "transformers"),
            Concept("Multi-Head Attention", "transformers"),
            Concept("Positional Encoding", "transformers"),
            Concept("Layer Normalization", "transformers"),
            Concept("Residual Connection", "transformers"),
            Concept("Feed Forward Network", "transformers"),
            Concept("Softmax", "transformers"),

            # Diffusion

            Concept("Diffusion Model", "diffusion"),
            Concept("Forward Process", "diffusion"),
            Concept("Reverse Process", "diffusion"),
            Concept("Noise Schedule", "diffusion"),
            Concept("Score Matching", "diffusion"),
            Concept("U-Net", "diffusion"),

            # Reinforcement Learning

            Concept("Markov Decision Process", "rl"),
            Concept("Bellman Equation", "rl"),
            Concept("Policy Gradient", "rl"),
            Concept("Value Function", "rl"),
            Concept("Q-Learning", "rl"),
            Concept("Actor-Critic", "rl"),

            # Graph ML

            Concept("Graph Neural Network", "graph_ml"),
            Concept("Message Passing", "graph_ml"),
            Concept("Graph Convolution", "graph_ml"),
            Concept("Graph Attention Network", "graph_ml"),
            Concept("Node Embedding", "graph_ml"),
        ]

    def all(self):

        return self._concepts
