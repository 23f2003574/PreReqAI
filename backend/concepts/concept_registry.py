from dataclasses import dataclass


@dataclass(frozen=True)
class Concept:

    name: str
    domain: str
    # Other spellings papers use for the same concept (acronyms, hyphen variants); matched as whole words.
    aliases: tuple = ()
    # An ambiguous concept is also an everyday word ("pay attention", "dropout rates", "the embedding of a stone"). It is counted only where
    # the text is technical: a bare mention needs corroboration (a `context` pattern, or the shared ML vocabulary, in the paper), while a
    # mention inside one of its `technical` phrases (lower-case regular expressions) always counts. Leave both empty for an unambiguous concept.
    ambiguous: bool = False
    technical: tuple = ()
    context: tuple = ()


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
            Concept("Attention", "transformers", ambiguous=True,
                    technical=(r"attention (?:mechanisms?|layers?|heads?|weights?|scores?|maps?|blocks?|modules?|is all you need)", r"(?:soft|hard|additive|dot-product|multiplicative|local|global|sparse|linear|causal|masked) attention"),
                    context=(r"transformers?", r"encoder|decoder", r"quer(?:y|ies)|keys?|values?", r"softmax", r"tokens?", r"sequences?")),
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
            Concept("Dropout", "deep_learning", ambiguous=True,
                    technical=(r"dropout (?:layers?|probabilit(?:y|ies)|masks?|regulari[sz]ation)", r"(?:apply|applied|applying|use|used|using|add|added) dropout", r"dropout (?:of|rate of|rate =|p =) ?0?\.\d+"),
                    context=(r"neural", r"layers?", r"hidden (?:units?|layers?)", r"regulari[sz]", r"weights?", r"activations?", r"co-adapt")),
            Concept("Recurrent Neural Network", "deep_learning", aliases=('RNN', 'RNNs', 'LSTM', 'LSTMs', 'GRU', 'long short-term memory', 'recurrent network')),
            Concept("Adam Optimizer", "deep_learning", aliases=('AdamW', 'Adam optimiser')),
            Concept("Large Language Model", "transformers", aliases=('LLM', 'BERT', 'GPT')),
            Concept("Cross-Entropy Loss", "deep_learning", aliases=('cross entropy', 'negative log-likelihood')),
            Concept("Maximum Likelihood Estimation", "probability", aliases=('maximum likelihood', 'MLE')),
            Concept("Overfitting", "deep_learning", aliases=('overfit', 'overfitted', 'over-fit', 'over-fitted', 'over-fitting'), ambiguous=True,
                    technical=(r"overfitt?(?:ed|ing)? (?:to|on) (?:the )?(?:training|data)", r"(?:prevent|reduce|avoid|mitigate|combat|risk of|reduces|prevents) over-?fit(?:ting)?", r"over-?fitting (?:problem|risk|gap)"),
                    context=(r"training", r"validation", r"generali[sz]", r"regulari[sz]", r"datasets?", r"neural", r"parameters")),
            Concept("Embedding", "deep_learning", aliases=('word2vec',), ambiguous=True,
                    technical=(r"(?:word|token|sentence|node|graph|positional|input|output|learned|pre-?trained|text|image|entity|vector|dense|sinusoidal|contextual) embeddings?", r"embeddings? (?:layers?|matri(?:x|ces)|vectors?|spaces?|tables?|dimensions?|models?)"),
                    context=(r"vectors?", r"neural", r"tokens?", r"vocabular", r"lookup", r"dimension", r"cosine", r"semantic")),
            Concept("Fine-Tuning", "transformers", aliases=('fine tuning', 'finetuning', 'fine tune', 'fine tuned', 'fine-tune', 'fine-tuned')),
            Concept("Monte Carlo Method", "probability", aliases=('Monte Carlo', 'MCMC')),
            Concept("Variational Autoencoder", "deep_learning", aliases=('VAE', 'variational auto-encoder')),
            Concept("Generative Adversarial Network", "deep_learning", aliases=('GAN',)),
            Concept("Variational Inference", "probability", aliases=('ELBO', 'evidence lower bound', 'variational lower bound', 'variational bound')),

            # Added: parameter-efficient adaptation, alignment, representation learning, tokenisation, vision transformers

            Concept("Parameter-Efficient Fine-Tuning", "transformers", aliases=('PEFT', 'parameter efficient fine-tuning', 'parameter-efficient finetuning')),
            Concept("LoRA", "transformers", aliases=('low-rank adaptation', 'low rank adaptation')),
            Concept("Reinforcement Learning from Human Feedback", "rl", aliases=('RLHF',)),
            Concept("Proximal Policy Optimization", "rl", aliases=('PPO',)),
            Concept("Contrastive Learning", "deep_learning", aliases=('contrastive loss', 'InfoNCE')),
            Concept("Tokenization", "transformers", aliases=('tokenisation', 'tokenizer', 'tokeniser', 'byte-pair encoding', 'byte pair encoding', 'BPE', 'WordPiece')),
            Concept("Vision Transformer", "transformers", aliases=('ViT',)),

            # Diffusion

            Concept("Diffusion Model", "diffusion", aliases=('DDPM', 'denoising diffusion', 'diffusion probabilistic model')),
            Concept("Forward Process", "diffusion"),
            Concept("Reverse Process", "diffusion"),
            Concept("Noise Schedule", "diffusion"),
            Concept("Score Matching", "diffusion"),
            Concept("U-Net", "diffusion", aliases=('UNet',)),

            # Reinforcement Learning

            Concept("Reinforcement Learning", "rl"),
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

            # Classical machine learning and statistics

            Concept("Principal Component Analysis", "classical_ml", aliases=('PCA',)),
            Concept("Support Vector Machine", "classical_ml", aliases=('SVM',)),
            Concept("K-Means Clustering", "classical_ml", aliases=('k-means', 'k means', 'kmeans')),
            Concept("Decision Tree", "classical_ml"),
            Concept("Random Forest", "classical_ml"),
            Concept("Logistic Regression", "classical_ml"),
            Concept("Regularization", "classical_ml", aliases=('regularisation', 'weight decay', 'L1 penalty', 'L2 penalty')),
            Concept("Cross-Validation", "classical_ml", aliases=('cross validation', 'k-fold cross-validation', 'k-fold cross validation')),

            # Representation learning and modern AI systems (no bare 'distillation', 'SSL' or 'retrieval': each also means something else)

            Concept("Knowledge Distillation", "deep_learning", aliases=('model distillation', 'teacher-student distillation', 'distilling knowledge')),
            Concept("Retrieval-Augmented Generation", "transformers", aliases=('RAG', 'retrieval augmented generation')),
            Concept("Beam Search", "deep_learning", aliases=('beam decoding',)),
            Concept("Autoencoder", "deep_learning", aliases=('auto-encoder', 'denoising autoencoder', 'sparse autoencoder')),
            Concept("Self-Supervised Learning", "deep_learning", aliases=('self supervised learning', 'self-supervised', 'self supervised')),
            Concept("Transfer Learning", "deep_learning"),
        ]

    def all(self):

        return self._concepts
