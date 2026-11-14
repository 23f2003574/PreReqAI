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

    "Principal Component Analysis": [

        {
            "question":
                "What does the first principal component of a dataset represent?",

            "answer":
                "The direction along which the data varies the most.",

            "difficulty":
                "Easy",
        },
    ],


    "Support Vector Machine": [

        {
            "question":
                "What is the margin that a support vector machine maximises?",

            "answer":
                "The distance between the separating boundary and the nearest training points of each class.",

            "difficulty":
                "Medium",
        },
    ],


    "K-Means Clustering": [

        {
            "question":
                "What two steps does k-means repeat until the clusters stop changing?",

            "answer":
                "It assigns each point to its nearest centre and then moves each centre to the mean of its points.",

            "difficulty":
                "Easy",
        },
    ],


    "Decision Tree": [

        {
            "question":
                "What does a decision tree choose when it splits a node?",

            "answer":
                "The feature and threshold that most reduce impurity, such as entropy or Gini, in the child nodes.",

            "difficulty":
                "Easy",
        },
    ],


    "Random Forest": [

        {
            "question":
                "Why does averaging many trees in a random forest help?",

            "answer":
                "It lowers the variance of a single overfitted tree because the trees, trained on different samples, make different errors.",

            "difficulty":
                "Medium",
        },
    ],


    "Logistic Regression": [

        {
            "question":
                "What does logistic regression output for an input?",

            "answer":
                "The probability of the positive class, found by passing a weighted sum of the features through the sigmoid function.",

            "difficulty":
                "Easy",
        },
    ],


    "Regularization": [

        {
            "question":
                "Why does an L2 penalty on the weights reduce overfitting?",

            "answer":
                "It discourages large weights, which limits the model's complexity so it fits noise in the training data less.",

            "difficulty":
                "Medium",
        },
    ],


    "Cross-Validation": [

        {
            "question":
                "In k-fold cross-validation, what is each fold used for?",

            "answer":
                "Each fold is held out once as the test set while the model is trained on the other folds.",

            "difficulty":
                "Easy",
        },
    ],
}


# Questions for the foundational prerequisite subjects of the study plans (not registry concepts, so they are kept apart from QUIZ_BANK).
# Same schema as QUIZ_BANK: an answer states the correct answer and why. They are served only when a subject is asked for by name.
SUBJECT_QUIZ_BANK = {
    "Linear Algebra": [
        {"question": "What does multiplying a vector by a matrix do geometrically?", "answer": "It applies a linear transformation to the vector, such as a rotation, scaling or projection, because each output entry is a weighted sum of the input entries.", "difficulty": "Easy"},
        {"question": "What is an eigenvector of a matrix A?", "answer": "A non-zero vector whose direction is unchanged by A, which only scales it by a factor called the eigenvalue, so that Av equals lambda times v.", "difficulty": "Medium"},
        {"question": "What does the rank of a matrix tell you?", "answer": "It is the number of linearly independent rows or columns, which equals the dimension of the space the matrix can map onto.", "difficulty": "Medium"},
    ],
    "Probability": [
        {"question": "What is the difference between a joint and a conditional probability?", "answer": "The joint probability P(A, B) is that both events happen, while the conditional P(A | B) is the probability of A given that B is already known to have happened.", "difficulty": "Easy"},
        {"question": "What does Bayes' rule compute?", "answer": "It computes the posterior P(A | B) from the likelihood P(B | A), the prior P(A) and the evidence P(B), as P(B | A) P(A) divided by P(B).", "difficulty": "Medium"},
        {"question": "What is the expected value of a random variable?", "answer": "It is the probability-weighted average of all its possible values, the long-run mean over many independent draws.", "difficulty": "Easy"},
    ],
    "Calculus": [
        {"question": "What does the derivative of a function at a point measure?", "answer": "It measures the instantaneous rate of change of the function there, which is the slope of the tangent line at that point.", "difficulty": "Easy"},
        {"question": "What does the chain rule say about the derivative of f(g(x))?", "answer": "It equals the derivative of f evaluated at g(x) multiplied by the derivative of g at x, which is how gradients are passed back through layers.", "difficulty": "Medium"},
        {"question": "What is a partial derivative?", "answer": "It is the derivative of a function of several variables with respect to one of them while all the other variables are held fixed.", "difficulty": "Easy"},
    ],
    "Information Theory": [
        {"question": "What does the entropy of a distribution measure?", "answer": "It measures the average uncertainty or surprise of its outcomes, which is the expected number of bits needed to encode a draw from it.", "difficulty": "Medium"},
        {"question": "What does KL divergence measure between two distributions P and Q?", "answer": "It measures how much extra information is needed to encode samples from P using a code built for Q, and it is zero only when the two distributions are identical.", "difficulty": "Medium"},
        {"question": "What is mutual information between two variables?", "answer": "It is the reduction in uncertainty about one variable gained by knowing the other, and it is zero exactly when they are independent.", "difficulty": "Hard"},
    ],
    "Optimization": [
        {"question": "Why does gradient descent move against the gradient?", "answer": "The gradient points in the direction of steepest increase of the function, so stepping the opposite way decreases it most quickly for a small enough step.", "difficulty": "Easy"},
        {"question": "What goes wrong if the learning rate is too large?", "answer": "The steps overshoot the minimum, so the loss can oscillate or diverge instead of decreasing steadily.", "difficulty": "Easy"},
        {"question": "Why is a convex function easy to minimise?", "answer": "Every local minimum of a convex function is also a global minimum, so a descent method cannot get stuck in a worse local minimum.", "difficulty": "Medium"},
    ],
    "Statistics": [
        {"question": "What does a 95 percent confidence interval mean?", "answer": "The procedure that produced the interval would contain the true parameter in about 95 percent of repeated samples, not that the parameter has a 95 percent chance of lying in one interval.", "difficulty": "Hard"},
        {"question": "What is the bias-variance trade-off?", "answer": "A simpler model tends to have high bias and low variance while a flexible one has low bias and high variance, so expected error is balanced between the two.", "difficulty": "Medium"},
        {"question": "What does a p-value represent in a hypothesis test?", "answer": "It is the probability of seeing data at least as extreme as observed if the null hypothesis were true, so a small value is evidence against that hypothesis.", "difficulty": "Medium"},
    ],
    "Stochastic Processes": [
        {"question": "What is the Markov property of a process?", "answer": "The future of the process depends only on its present state and not on how it arrived there, so the history adds no further information.", "difficulty": "Easy"},
        {"question": "What is a random walk?", "answer": "A process whose position changes at each step by a random increment, so its position is the running sum of independent random steps.", "difficulty": "Easy"},
        {"question": "What does the stationary distribution of a Markov chain describe?", "answer": "It is a distribution over states that stays unchanged after one more transition, and the long-run fraction of time spent in each state of a well-behaved chain converges to it.", "difficulty": "Hard"},
    ],
    "Neural Networks": [
        {"question": "Why does a neural network need non-linear activation functions?", "answer": "Without them a stack of layers collapses into a single linear map, so the network could not represent non-linear relationships.", "difficulty": "Easy"},
        {"question": "What does a single neuron compute?", "answer": "It computes a weighted sum of its inputs plus a bias and passes the result through an activation function.", "difficulty": "Easy"},
        {"question": "What is one training step of a neural network?", "answer": "It runs a forward pass to get the loss, backpropagates the gradient of the loss to every weight, and then updates the weights with an optimiser step.", "difficulty": "Medium"},
    ],
    "Graphs": [
        {"question": "What do the nodes and edges of a graph represent?", "answer": "Nodes represent entities and edges represent relationships between pairs of them, which may be directed or undirected.", "difficulty": "Easy"},
        {"question": "What does the adjacency matrix of a graph store?", "answer": "Entry (i, j) records whether, or with what weight, there is an edge from node i to node j, so the whole graph structure is one matrix.", "difficulty": "Easy"},
        {"question": "What is the degree of a node?", "answer": "It is the number of edges attached to the node, counted as in-degree and out-degree for a directed graph.", "difficulty": "Easy"},
    ],
}
