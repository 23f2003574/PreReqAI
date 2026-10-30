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
}
