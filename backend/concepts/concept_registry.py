from dataclasses import dataclass


@dataclass(frozen=True)
class Concept:

    name: str
    domain: str
    # Other spellings papers use for the same concept (acronyms, hyphen variants); matched as whole words.
    aliases: tuple = ()


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
            Concept("Self-Attention", "transformers", aliases=('self attention',)),
            Concept("Cross-Attention", "transformers", aliases=('cross attention',)),
            Concept("Multi-Head Attention", "transformers", aliases=('MHA', 'multi head attention', 'multihead attention')),
            Concept("Positional Encoding", "transformers", aliases=('position encoding', 'positional embedding')),
            Concept("Layer Normalization", "transformers", aliases=('LayerNorm', 'layer norm', 'layer normalisation')),
            Concept("Residual Connection", "transformers", aliases=('skip connection', 'residual link')),
            Concept("Feed Forward Network", "transformers", aliases=('FFN', 'feed-forward network')),
            Concept("Softmax", "transformers"),

            # Deep learning fundamentals

            Concept("Gradient Descent", "deep_learning", aliases=('SGD', 'stochastic gradient descent')),
            Concept("Backpropagation", "deep_learning", aliases=('backprop', 'back-propagation')),
            Concept("Convolutional Neural Network", "deep_learning", aliases=('CNN', 'CNNs', 'convolutional network')),
            Concept("Batch Normalization", "deep_learning", aliases=('BatchNorm', 'batch norm', 'batch normalisation')),
            Concept("Dropout", "deep_learning"),
            Concept("Recurrent Neural Network", "deep_learning", aliases=('RNN', 'RNNs', 'LSTM', 'LSTMs', 'GRU', 'long short-term memory', 'recurrent network')),
            Concept("Adam Optimizer", "deep_learning", aliases=('AdamW', 'Adam optimiser')),

            # Diffusion

            Concept("Diffusion Model", "diffusion", aliases=('DDPM', 'denoising diffusion', 'diffusion probabilistic model')),
            Concept("Forward Process", "diffusion"),
            Concept("Reverse Process", "diffusion"),
            Concept("Noise Schedule", "diffusion"),
            Concept("Score Matching", "diffusion"),
            Concept("U-Net", "diffusion", aliases=('UNet',)),

            # Reinforcement Learning

            Concept("Markov Decision Process", "rl", aliases=('MDP', 'MDPs')),
            Concept("Bellman Equation", "rl"),
            Concept("Policy Gradient", "rl"),
            Concept("Value Function", "rl"),
            Concept("Q-Learning", "rl", aliases=('Q learning',)),
            Concept("Actor-Critic", "rl", aliases=('actor critic',)),

            # Graph ML

            Concept("Graph Neural Network", "graph_ml", aliases=('GNN', 'GNNs')),
            Concept("Message Passing", "graph_ml"),
            Concept("Graph Convolution", "graph_ml", aliases=('GCN', 'GCNs', 'graph convolutional', 'graph convolutional network')),
            Concept("Graph Attention Network", "graph_ml", aliases=('GAT', 'GATs')),
            Concept("Node Embedding", "graph_ml"),
        ]

    def all(self):

        return self._concepts
