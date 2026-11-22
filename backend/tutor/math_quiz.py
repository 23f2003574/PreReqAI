"""Diagnostic questions for the mathematical subtopics a paper's equations need (backend/parsing/math_subtopics.py), served like any other question under the name "Math: <subtopic>".

Two questions per subtopic, each with an explanation. They are written by the maintainers (an AI assistant wrote this first set; no human has reviewed the wording), kept apart from QUIZ_BANK and
SUBJECT_QUIZ_BANK so those banks and their counts are unchanged. `distractors` for these come from the other subtopics of the same subject and the subject's own questions (diagnostic._siblings)."""
from .quiz_bank import QUIZ_EXPLANATIONS

PREFIX = "Math: "
# (subtopic, subject, [(question, answer, difficulty, explanation)])
_ROWS = [
    ("Expectation of a random variable", "Probability", [
        ("What does E[X] mean for a random variable X?", "The average value of X over its distribution, with each outcome weighted by how likely it is.", "Easy",
         "The expectation adds up every possible value times its probability, so it is the long-run average rather than the most likely value."),
        ("What does E over x drawn from D of f(x) say about a loss written this way?", "The loss f is averaged over samples x drawn from the distribution D, not computed on one example.", "Medium",
         "A subscript such as x ~ D tells you which distribution the average is taken over; in practice it is estimated by averaging over a batch of samples.")]),
    ("Sampling from a distribution (x ~ D)", "Probability", [
        ("What does the notation x ~ D say about x?", "x is a random value drawn from the distribution D, so it can differ each time it is drawn.", "Easy",
         "The tilde means 'is distributed as': x is not a fixed number but a draw from D, so anything computed from x is random too."),
        ("Why do papers estimate an expectation over x ~ D by averaging a batch of samples?", "The average of many independent draws approaches the true expectation, which cannot usually be computed exactly.", "Medium",
         "By the law of large numbers the sample mean converges to the expectation, so a minibatch average is an unbiased estimate of it.")]),
    ("Conditional probability", "Probability", [
        ("What does p(y | x) mean?", "The probability of y given that x is already known or fixed.", "Easy",
         "The bar reads 'given': the distribution of y once the value of x is held fixed, as when a language model predicts the next word from the words before it."),
        ("How are p(y | x), p(x, y) and p(x) related?", "The joint probability p(x, y) equals p(y | x) multiplied by p(x), so p(y | x) is the joint divided by p(x).", "Medium",
         "This is the definition of conditional probability, and it is why a joint distribution can be factorised into a chain of conditionals.")]),
    ("Softmax and normalised exponentials", "Probability", [
        ("What does softmax do to a vector of scores?", "It turns the scores into positive numbers that sum to one by exponentiating them and dividing by their total.", "Easy",
         "Exponentiation makes every score positive and larger scores dominate, and dividing by the sum makes the result a probability distribution."),
        ("What happens to the softmax output when one score is much larger than the others?", "Nearly all of the probability goes to the largest score, and the others come out close to zero.", "Medium",
         "Because of the exponential, a gap in scores becomes a much larger ratio in probabilities, which is why dividing the scores by a temperature changes how sharp the output is.")]),
    ("Gaussian distribution", "Probability", [
        ("What do the two parameters in N(mu, sigma^2) describe?", "The mean mu is the centre of the bell curve and the variance sigma squared is how widely it is spread.", "Easy",
         "A Gaussian is fully described by its mean and variance; the standard deviation sigma is the square root of the variance."),
        ("Why are Gaussians so common in machine learning papers?", "Sums of many small independent effects tend to be Gaussian, and the distribution is easy to work with because it has closed-form formulas.", "Medium",
         "The central limit theorem explains the first reason, and the closed forms for products, marginals and conditionals explain the second.")]),
    ("Variance and covariance", "Statistics", [
        ("What does the variance of a random variable measure?", "How far its values typically spread around its mean, as the average squared deviation from the mean.", "Easy",
         "Var[X] = E[(X - E[X])^2]: squaring the deviations stops positive and negative ones cancelling, so it measures spread."),
        ("What does a covariance of zero between two variables tell you?", "They have no linear relationship, although they can still depend on each other in a nonlinear way.", "Hard",
         "Covariance only captures linear association, so independent variables have zero covariance but zero covariance does not imply independence.")]),
    ("Kullback-Leibler divergence", "Information Theory", [
        ("What does the KL divergence between distributions p and q measure?", "How much extra information is needed when q is used to describe data that really come from p.", "Medium",
         "It is the expected log ratio of p to q under p, zero only when they are the same distribution and never negative."),
        ("Is the KL divergence from p to q the same as from q to p?", "No, it is not symmetric, so it is a measure of difference but not a distance.", "Medium",
         "KL(p || q) and KL(q || p) generally differ, and that is why papers state carefully which direction a method minimises.")]),
    ("Cross-entropy and log-likelihood", "Information Theory", [
        ("Why does minimising cross-entropy loss on labelled data fit the model's probabilities?", "It is the negative log-likelihood of the labels under the model, so lowering it raises the probability the model gives to the true labels.", "Medium",
         "Cross-entropy H(p, q) = -sum p log q equals the negative average log-probability the model assigns to the observed outcomes."),
        ("Why is the log of the likelihood used instead of the likelihood itself?", "It turns a product over examples into a sum, which is easier to optimise and avoids numbers too small to represent.", "Medium",
         "The logarithm is increasing, so the maximiser is unchanged, and sums of logs are numerically stable where products of many small probabilities underflow.")]),
    ("Logarithms and exponentials", "Calculus", [
        ("How are log(a * b) and log(a) + log(b) related?", "They are equal, because the logarithm of a product is the sum of the logarithms.", "Easy",
         "This identity is what lets a likelihood, which is a product, become a log-likelihood, which is a sum."),
        ("What is the relationship between exp and log?", "They are inverse functions, so the log of exp(x) is x and exp of log(x) is x for positive x.", "Easy",
         "Because they undo each other, a quantity written as an exponential can be handled by taking logs, and vice versa.")]),
    ("Sigmoid and logistic functions", "Calculus", [
        ("What range of values does the sigmoid function output?", "Values between zero and one, which is why it can be read as a probability.", "Easy",
         "sigma(x) = 1 / (1 + e^-x) is near 0 for very negative x, near 1 for very positive x and exactly 0.5 at x = 0."),
        ("What happens to the sigmoid's gradient when its input is very large or very small?", "The gradient becomes almost zero, so learning through a saturated sigmoid is very slow.", "Medium",
         "The derivative sigma(x)(1 - sigma(x)) is tiny at both tails, the vanishing-gradient problem of saturated units.")]),
    ("Gradients and partial derivatives", "Calculus", [
        ("What does the gradient of a loss with respect to the parameters point towards?", "The direction in which the loss increases fastest, so training steps go the opposite way.", "Easy",
         "Gradient descent subtracts a multiple of the gradient, moving the parameters towards lower loss."),
        ("What is a partial derivative?", "The rate of change of a function with respect to one variable while all the other variables are held fixed.", "Easy",
         "The gradient is the vector of partial derivatives, one per parameter, each measuring that parameter's own effect on the loss.")]),
    ("Integration", "Calculus", [
        ("What does an integral of a function over a range compute?", "The accumulated total of the function over that range, such as the area under its curve.", "Easy",
         "An integral is the continuous version of a sum, which is why expectations over continuous variables are written as integrals."),
        ("Why must a probability density integrate to one?", "The probability that the variable takes some value at all is one, and the integral adds up the probability of every value.", "Medium",
         "A density itself is not a probability; probabilities come from integrating it over a range, and the whole range must total one.")]),
    ("Summation and product notation", "Calculus", [
        ("How is a sum over i from 1 to n of a_i read?", "As a_1 plus a_2 and so on up to a_n, adding the term for every index in the range.", "Easy",
         "The index below and the limit above the sigma say which terms are added, and a capital pi means multiply them instead."),
        ("What does a capital pi over i of p(x_i) usually represent in a paper?", "The joint probability of independent examples, found by multiplying the probability of each one.", "Medium",
         "Independence lets probabilities multiply, and the log of that product is the sum used in log-likelihoods.")]),
    ("Matrix multiplication and transpose", "Linear Algebra", [
        ("When can two matrices A and B be multiplied as AB?", "When the number of columns of A equals the number of rows of B.", "Easy",
         "Each entry of AB is the dot product of a row of A with a column of B, which needs the two to have the same length."),
        ("What does the transpose K^T do in a product such as Q K^T?", "It swaps the rows and columns of K so that every query is compared by dot product with every key.", "Medium",
         "Q K^T has one entry for each query-key pair, which is the table of attention scores before softmax.")]),
    ("Vector norms and dot products", "Linear Algebra", [
        ("What does the dot product of two vectors measure?", "How aligned they are, large and positive when they point the same way and zero when they are perpendicular.", "Easy",
         "The dot product equals the product of the lengths times the cosine of the angle between the vectors."),
        ("Why is a dot product divided by the square root of the dimension in scaled attention?", "To stop the scores growing with the dimension, which would push softmax into regions with tiny gradients.", "Hard",
         "The variance of a dot product of random vectors grows with their dimension, and dividing by its square root keeps the scores at a stable size.")]),
    ("Optimisation objectives (argmin and argmax)", "Optimization", [
        ("What does argmin over theta of L(theta) denote?", "The value of theta that makes L(theta) as small as possible, rather than the minimum value itself.", "Easy",
         "min gives the smallest value of the loss while argmin gives the parameters at which it is reached, which is what training looks for."),
        ("How are minimising L and maximising minus L related?", "They have the same solution, because the point that makes L smallest makes minus L largest.", "Easy",
         "Papers switch between loss minimisation and objective maximisation freely because of this sign flip.")]),
]
MATH_QUIZ = {PREFIX + name: [{"question": q, "answer": a, "difficulty": d} for q, a, d, _ in rows] for name, _, rows in _ROWS}
MATH_SUBJECT = {PREFIX + name: subject for name, subject, _ in _ROWS}
for _name, _, _rows in _ROWS:
    for _q, _a, _d, _e in _rows:
        QUIZ_EXPLANATIONS[(PREFIX + _name, _q)] = _e
