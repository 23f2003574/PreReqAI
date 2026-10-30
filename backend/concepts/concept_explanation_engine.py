from backend.models import (
    Paper,
    ConceptExplanation,
)


class ConceptExplanationEngine:
    """
    Generates deterministic explanations for
    concepts currently supported by PreReqAI.
    """

    EXPLANATIONS = {

        "Transformer": (
            "A neural network architecture that processes sequences using attention mechanisms instead of recurrence.",
            "Intermediate",
        ),

        "Attention": (
            "A mechanism that allows a model to focus on the most relevant parts of an input sequence.",
            "Intermediate",
        ),

        "Multi-Head Attention": (
            "Multiple attention operations performed in parallel to capture different relationships within the input.",
            "Advanced",
        ),

        "Softmax": (
            "A mathematical function that converts scores into probabilities.",
            "Beginner",
        ),

        "Graph Neural Network": (
            "A neural network designed to learn from graph-structured data.",
            "Intermediate",
        ),

        "Self-Attention": (
            "Attention in which every position of a sequence attends to all other positions of the same sequence to build its representation.",
            "Intermediate",
        ),

        "Cross-Attention": (
            "Attention in which queries come from one sequence and keys and values from another, such as a decoder attending to an encoder's output.",
            "Advanced",
        ),

        "Positional Encoding": (
            "A signal added to token embeddings that tells an attention model where each token sits in the sequence, since attention alone ignores order.",
            "Intermediate",
        ),

        "Layer Normalization": (
            "Normalizing the activations of each example across its features to stabilise and speed up training of deep networks.",
            "Intermediate",
        ),

        "Residual Connection": (
            "A shortcut that adds a layer's input to its output so gradients flow easily and very deep networks can be trained.",
            "Beginner",
        ),

        "Feed Forward Network": (
            "A position-wise fully connected network applied to each token independently, typically after the attention sublayer in a Transformer block.",
            "Beginner",
        ),

        "Diffusion Model": (
            "A generative model that learns to reverse a gradual noising process in order to turn random noise into realistic samples.",
            "Advanced",
        ),

        "Forward Process": (
            "The fixed process in a diffusion model that gradually adds noise to data until it becomes almost pure noise.",
            "Intermediate",
        ),

        "Reverse Process": (
            "The learned process in a diffusion model that removes noise step by step to recover data from pure noise.",
            "Advanced",
        ),

        "Noise Schedule": (
            "The rule that sets how much noise is added at each step of a diffusion model's forward process.",
            "Intermediate",
        ),

        "Score Matching": (
            "Training a model to estimate the gradient of the log data density (the score), which guides sampling in score-based diffusion models.",
            "Advanced",
        ),

        "U-Net": (
            "A convolutional encoder-decoder with skip connections between matching resolutions, widely used as the denoising network in diffusion models.",
            "Intermediate",
        ),

        "Markov Decision Process": (
            "The standard mathematical model of sequential decision making: states, actions, transition probabilities and rewards, where the next state depends only on the current state and action.",
            "Intermediate",
        ),

        "Bellman Equation": (
            "A recursive relation that expresses the value of a state as the immediate reward plus the discounted value of the states that follow.",
            "Advanced",
        ),

        "Policy Gradient": (
            "A family of reinforcement learning methods that improve a policy directly by following the gradient of expected return.",
            "Advanced",
        ),

        "Value Function": (
            "The expected return an agent can obtain from a state (or state-action pair) when following a given policy.",
            "Intermediate",
        ),

        "Q-Learning": (
            "An off-policy reinforcement learning algorithm that learns the value of each state-action pair and acts greedily on it.",
            "Intermediate",
        ),

        "Actor-Critic": (
            "A reinforcement learning architecture that trains a policy (the actor) together with a value estimate (the critic) that reduces the variance of its updates.",
            "Advanced",
        ),

        "Message Passing": (
            "The step in which each graph node updates its representation by aggregating messages from its neighbours.",
            "Intermediate",
        ),

        "Graph Convolution": (
            "A convolution-like operation that combines each node's features with those of its neighbours, using the graph's structure instead of a regular grid.",
            "Advanced",
        ),

        "Gradient Descent": (
            "An optimisation method that repeatedly moves model parameters a small step against the gradient of the loss to reduce it.",
            "Beginner",
        ),

        "Backpropagation": (
            "The algorithm that computes the loss gradient for every weight of a neural network by applying the chain rule backwards through its layers.",
            "Intermediate",
        ),

        "Convolutional Neural Network": (
            "A neural network that slides small learned filters over its input, reusing the same weights at every position, mainly for images.",
            "Intermediate",
        ),

        "Batch Normalization": (
            "A layer that normalises activations using the statistics of the current mini-batch to make deep networks train faster and more stably.",
            "Intermediate",
        ),

        "Dropout": (
            "A regularisation technique that randomly switches off units during training so the network cannot over-rely on any one of them.",
            "Beginner",
        ),

        "Recurrent Neural Network": (
            "A neural network that reads a sequence one step at a time and carries a hidden state forward, so each output can depend on what came before (LSTM and GRU are gated variants).",
            "Intermediate",
        ),

        "Reinforcement Learning": (
            "Learning to act by trial and error: an agent interacts with an environment and adjusts its behaviour to maximise the cumulative reward it receives.",
            "Intermediate",
        ),

        "Large Language Model": (
            "A very large Transformer trained on text to predict the next token (GPT) or masked tokens (BERT), whose learned representations are reused for many language tasks.",
            "Intermediate",
        ),

        "Cross-Entropy Loss": (
            "The standard loss for classification and language modelling: the negative log-probability a model assigns to the correct answer.",
            "Beginner",
        ),

        "Maximum Likelihood Estimation": (
            "Choosing the model parameters that make the observed data most probable, usually by maximising the log-likelihood.",
            "Intermediate",
        ),

        "Overfitting": (
            "When a model fits noise in its training data so well that it performs worse on new data; countered by regularisation, dropout, early stopping and more data.",
            "Beginner",
        ),

        "Fine-Tuning": (
            "Continuing to train a pretrained model on a smaller task-specific dataset so that its learned representations adapt to the new task.",
            "Intermediate",
        ),

        "Monte Carlo Method": (
            "Estimating a quantity by averaging over many random samples, as in sampling-based inference (MCMC) and return estimation in reinforcement learning.",
            "Intermediate",
        ),

        "Variational Autoencoder": (
            "A generative model with an encoder that maps data to a distribution over latent variables and a decoder that reconstructs it, trained by maximising the evidence lower bound.",
            "Advanced",
        ),

        "Generative Adversarial Network": (
            "A generative model in which a generator and a discriminator are trained against each other, so the generator learns to produce samples the discriminator cannot tell from real data.",
            "Advanced",
        ),

        "Variational Inference": (
            "Approximating an intractable posterior distribution with a simpler one by maximising the evidence lower bound (ELBO), which is equivalent to minimising their KL divergence.",
            "Advanced",
        ),

        "Adam Optimizer": (
            "A gradient-based optimiser that keeps running averages of each parameter's gradient and squared gradient to adapt its step size per parameter.",
            "Intermediate",
        ),

        "Graph Attention Network": (
            "A graph neural network that learns attention weights over each node's neighbours instead of treating them equally.",
            "Advanced",
        ),

        "Node Embedding": (
            "A low-dimensional vector representation of a graph node that preserves information about its neighbourhood and role in the graph.",
            "Intermediate",
        ),
    }

    def explain(
        self,
        paper: Paper,
    ) -> Paper:

        paper.concept_explanations.clear()

        for concept in paper.concepts:

            if concept.name not in self.EXPLANATIONS:

                continue

            definition, difficulty = (
                self.EXPLANATIONS[
                    concept.name
                ]
            )

            paper.concept_explanations.append(

                ConceptExplanation(

                    concept=concept.name,

                    definition=definition,

                    difficulty=difficulty,
                )
            )

        return paper
