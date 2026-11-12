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
}
