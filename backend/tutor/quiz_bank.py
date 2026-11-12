QUIZ_BANK = {

    "Attention": [

        {
            "question":
                "What is the primary purpose of the Attention mechanism?",

            "answer":
                "To assign greater importance to the most relevant parts of the input.",

            "difficulty":
                "Easy",
        },

        {
            "question":
                "Why is Self-Attention more parallelizable than an RNN?",

            "answer":
                "Because every token can be processed simultaneously.",

            "difficulty":
                "Medium",
        },
    ],

    "Transformer": [

        {
            "question":
                "Why are positional encodings required?",

            "answer":
                "Transformers do not inherently encode token order.",

            "difficulty":
                "Medium",
        },
    ],

    "Softmax": [

        {
            "question":
                "Why does Softmax produce probabilities instead of raw scores?",

            "answer":
                "Because it normalizes values into a probability distribution.",

            "difficulty":
                "Easy",
        },
    ],

    "Backpropagation": [
        {"question": "What does backpropagation compute?",
         "answer": "The gradient of the loss with respect to every weight, by applying the chain rule backwards through the network.",
         "difficulty": "Easy"},
    ],

    "Cross-Entropy Loss": [
        {"question": "What does cross-entropy loss penalise?",
         "answer": "A low probability assigned to the correct class: the loss is the negative log-probability of the right answer.",
         "difficulty": "Easy"},
    ],

    "Overfitting": [
        {"question": "How can you tell that a model is overfitting?",
         "answer": "Its training error keeps falling while its error on held-out data stops improving or rises.",
         "difficulty": "Easy"},
        {"question": "Name two ways to reduce overfitting.",
         "answer": "Regularisation (such as dropout or weight decay) and more training data; early stopping also helps.",
         "difficulty": "Medium"},
    ],

    "Reinforcement Learning": [
        {"question": "What does a reinforcement learning agent try to maximise?",
         "answer": "The cumulative reward it receives from the environment over time.",
         "difficulty": "Easy"},
    ],

    "Diffusion Model": [
        {"question": "What does a diffusion model learn to do?",
         "answer": "Reverse a process that gradually adds noise to data, so that new samples can be generated from pure noise.",
         "difficulty": "Medium"},
    ],

    "Variational Autoencoder": [
        {"question": "What does the KL term in a variational autoencoder's objective do?",
         "answer": "It keeps the encoder's latent distribution close to the prior, so the latent space can be sampled from.",
         "difficulty": "Hard"},
    ],
    "Gradient Descent": [
        {"question": "In which direction does gradient descent move the parameters at each step?",
         "answer": "Against the gradient of the loss, i.e. the direction in which the loss decreases fastest.",
         "difficulty": "Easy"},
        {"question": "What goes wrong if the learning rate is set too large?",
         "answer": "The updates overshoot the minimum, so the loss oscillates or diverges instead of decreasing.",
         "difficulty": "Medium"},
    ],

    "Adam Optimizer": [
        {"question": "What two running statistics of the gradient does Adam keep for each parameter?",
         "answer": "An exponential moving average of the gradient (momentum) and of its square (scale), used to adapt the step size.",
         "difficulty": "Medium"},
    ],

    "Dropout": [
        {"question": "How does dropout reduce overfitting?",
         "answer": "It randomly zeroes units during training, so the network cannot rely on any single unit and learns more robust features.",
         "difficulty": "Easy"},
    ],

    "Self-Attention": [

        {
            "question":
                "Where do the queries, keys and values of Self-Attention come from?",

            "answer":
                "All three are computed from the same input sequence.",

            "difficulty":
                "Easy",
        },

        {
            "question":
                "Why are Self-Attention scores divided by the square root of the key dimension?",

            "answer":
                "To keep the dot products small so the Softmax does not saturate and gradients stay useful.",

            "difficulty":
                "Medium",
        },
    ],

    "Multi-Head Attention": [

        {
            "question":
                "Why use several attention heads instead of one?",

            "answer":
                "Each head can attend to a different kind of relationship in a different subspace.",

            "difficulty":
                "Medium",
        },
    ],

    "Positional Encoding": [

        {
            "question":
                "What problem does Positional Encoding solve?",

            "answer":
                "Attention alone ignores token order, so position information must be added to the embeddings.",

            "difficulty":
                "Easy",
        },
    ],

    "Layer Normalization": [

        {
            "question":
                "What does Layer Normalization normalize over?",

            "answer":
                "The features of each individual example, not across the batch.",

            "difficulty":
                "Medium",
        },
    ],

    "Residual Connection": [

        {
            "question":
                "Why do Residual Connections make deep networks easier to train?",

            "answer":
                "They give gradients a direct path around each layer.",

            "difficulty":
                "Easy",
        },
    ],

    "Feed Forward Network": [

        {
            "question":
                "What does the Feed Forward Network do in a Transformer block?",

            "answer":
                "It applies the same two-layer nonlinear transform to each token position independently.",

            "difficulty":
                "Medium",
        },
    ],

    "LoRA": [

        {
            "question":
                "What does LoRA train instead of the full pretrained weights?",

            "answer":
                "Two small low-rank matrices whose product is added to a frozen weight matrix.",

            "difficulty":
                "Medium",
        },
    ],

    "Proximal Policy Optimization": [

        {
            "question":
                "Why does PPO clip its objective?",

            "answer":
                "To stop a single update from moving the policy too far from the one that collected the data, which keeps training stable.",

            "difficulty":
                "Medium",
        },
    ],

    "Tokenization": [

        {
            "question":
                "Why do language models use subword tokenization such as byte-pair encoding instead of whole words?",

            "answer":
                "It keeps the vocabulary small while still representing rare and unseen words as sequences of known pieces.",

            "difficulty":
                "Easy",
        },
    ],

    "Vision Transformer": [

        {
            "question":
                "How does a Vision Transformer turn an image into a sequence?",

            "answer":
                "It cuts the image into fixed-size patches and embeds each patch as one token.",

            "difficulty":
                "Easy",
        },
    ],

    "Cross-Attention": [

        {
            "question":
                "In cross-attention, where do the queries come from compared with the keys and values?",

            "answer":
                "The queries come from one sequence (such as the decoder) while the keys and values come from another (such as the encoder output).",

            "difficulty":
                "Medium",
        },
    ],

    "Recurrent Neural Network": [

        {
            "question":
                "Why can an RNN not process all positions of a sequence in parallel during training?",

            "answer":
                "Each hidden state depends on the previous one, so the steps must be computed in order.",

            "difficulty":
                "Medium",
        },
    ],

    "Convolutional Neural Network": [

        {
            "question":
                "What does weight sharing in a convolutional layer achieve?",

            "answer":
                "The same small filter is applied at every position, which needs far fewer parameters and detects a pattern wherever it appears.",

            "difficulty":
                "Easy",
        },
    ],

    "Batch Normalization": [

        {
            "question":
                "What does batch normalization compute its statistics over?",

            "answer":
                "The mean and variance of each feature over the current mini-batch, before a learned scale and shift.",

            "difficulty":
                "Medium",
        },
    ],

    "Maximum Likelihood Estimation": [

        {
            "question":
                "What does maximum likelihood estimation choose?",

            "answer":
                "The parameters under which the observed data has the highest probability.",

            "difficulty":
                "Easy",
        },
    ],

    "Fine-Tuning": [

        {
            "question":
                "What is fine-tuning?",

            "answer":
                "Continuing to train a pretrained model on a smaller task-specific dataset so that it adapts to the new task.",

            "difficulty":
                "Easy",
        },
    ],

    "Embedding": [

        {
            "question":
                "What property should an embedding space have?",

            "answer":
                "Items that are similar should be close together as vectors.",

            "difficulty":
                "Easy",
        },
    ],

    "Markov Decision Process": [

        {
            "question":
                "What does the Markov property say in a Markov decision process?",

            "answer":
                "The next state and reward depend only on the current state and action, not on the earlier history.",

            "difficulty":
                "Medium",
        },
    ],

    "Bellman Equation": [

        {
            "question":
                "What does the Bellman equation express?",

            "answer":
                "The value of a state equals the immediate reward plus the discounted value of the states that follow.",

            "difficulty":
                "Medium",
        },
    ],

    "Policy Gradient": [

        {
            "question":
                "What do policy gradient methods optimise directly?",

            "answer":
                "The parameters of the policy, by following the gradient of the expected return.",

            "difficulty":
                "Medium",
        },
    ],

    "Value Function": [

        {
            "question":
                "What does a value function estimate?",

            "answer":
                "The expected return an agent obtains from a state (or state and action) when it follows a given policy.",

            "difficulty":
                "Easy",
        },
    ],

    "Q-Learning": [

        {
            "question":
                "Is Q-learning on-policy or off-policy, and why?",

            "answer":
                "Off-policy: it updates toward the best next action's value, whatever action the behaviour policy actually takes.",

            "difficulty":
                "Hard",
        },
    ],

    "Actor-Critic": [

        {
            "question":
                "What are the two parts of an actor-critic method?",

            "answer":
                "An actor that chooses actions (the policy) and a critic that estimates values to judge them.",

            "difficulty":
                "Medium",
        },
    ],

    "Graph Neural Network": [

        {
            "question":
                "What does a graph neural network update at each layer?",

            "answer":
                "Each node's representation, computed from its own features and those of its neighbours.",

            "difficulty":
                "Medium",
        },
    ],

    "Message Passing": [

        {
            "question":
                "What are the two steps of a message passing layer?",

            "answer":
                "Nodes aggregate messages from their neighbours, then update their own state from the aggregate.",

            "difficulty":
                "Medium",
        },
    ],

    "Graph Convolution": [

        {
            "question":
                "What does a graph convolution do to a node's features?",

            "answer":
                "It combines them with those of neighbouring nodes using normalised weights, like a filter over the graph.",

            "difficulty":
                "Medium",
        },
    ],

    "Graph Attention Network": [

        {
            "question":
                "How does a graph attention network differ from a plain graph convolution?",

            "answer":
                "It learns attention weights so each neighbour contributes with a different importance instead of fixed weights.",

            "difficulty":
                "Medium",
        },
    ],

    "Generative Adversarial Network": [

        {
            "question":
                "What are the two networks in a GAN and what do they do?",

            "answer":
                "A generator that creates samples and a discriminator that tries to tell them from real data; each trains against the other.",

            "difficulty":
                "Easy",
        },
    ],

    "Monte Carlo Method": [

        {
            "question":
                "Why do Monte Carlo methods work for estimating an expectation?",

            "answer":
                "The average of many random samples converges to the true expectation as the number of samples grows.",

            "difficulty":
                "Easy",
        },
    ],

    "Variational Inference": [

        {
            "question":
                "What does variational inference do to approximate a hard posterior?",

            "answer":
                "It picks the closest distribution from a simpler family by maximising a lower bound (the ELBO) on the data likelihood.",

            "difficulty":
                "Hard",
        },
    ],

    "Large Language Model": [

        {
            "question":
                "What is a large language model trained to do?",

            "answer":
                "Predict text, typically the next token, from very large amounts of data.",

            "difficulty":
                "Easy",
        },
    ],

    "Contrastive Learning": [

        {
            "question":
                "What does a contrastive loss do to embeddings?",

            "answer":
                "It pulls together embeddings of related (positive) examples and pushes apart those of unrelated (negative) ones.",

            "difficulty":
                "Medium",
        },
    ],

    "Score Matching": [

        {
            "question":
                "What is the score that score matching learns?",

            "answer":
                "The gradient of the log data density with respect to the input.",

            "difficulty":
                "Hard",
        },
    ],

    "U-Net": [

        {
            "question":
                "Why does a U-Net have skip connections between its encoder and decoder?",

            "answer":
                "They pass fine spatial detail directly to the decoder so it is not lost while downsampling.",

            "difficulty":
                "Medium",
        },
    ],

    "Forward Process": [

        {
            "question":
                "What happens in the forward process of a diffusion model?",

            "answer":
                "Noise is added to the data step by step until it is close to pure noise.",

            "difficulty":
                "Easy",
        },
    ],

    "Reverse Process": [

        {
            "question":
                "What does the reverse process of a diffusion model learn?",

            "answer":
                "To remove the noise step by step, turning noise back into a data sample.",

            "difficulty":
                "Medium",
        },
    ],

    "Noise Schedule": [

        {
            "question":
                "What does the noise schedule of a diffusion model set?",

            "answer":
                "How much noise is added at each step of the forward process.",

            "difficulty":
                "Easy",
        },
    ],

    "Parameter-Efficient Fine-Tuning": [

        {
            "question":
                "Why is parameter-efficient fine-tuning cheaper than full fine-tuning?",

            "answer":
                "Only a small number of added or selected parameters are trained while the pretrained weights stay frozen.",

            "difficulty":
                "Easy",
        },
    ],

    "Reinforcement Learning from Human Feedback": [

        {
            "question":
                "What is the role of the reward model in RLHF?",

            "answer":
                "It is trained on human preference comparisons and then supplies the reward used to optimise the model with reinforcement learning.",

            "difficulty":
                "Medium",
        },
    ],

    "Node Embedding": [

        {
            "question":
                "What is a node embedding?",

            "answer":
                "A learned vector for a graph node that captures its position and neighbourhood so similar nodes lie close together.",

            "difficulty":
                "Easy",
        },
    ],
}
