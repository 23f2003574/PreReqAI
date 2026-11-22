"""The specific mathematical skills a paper's equations call for, found from the equations themselves (not from the broad subject of the paper).

Each rule recognises a notation (an expectation, a KL divergence, a gradient, a matrix product, a softmax, a conditional probability...) in an equation's text and names the subtopic a
learner must be able to read it with, the broad subject it belongs to (one PreReqAI already plans and has resources for) and a one-line reason. A recommendation always carries the equations
that produced it (number, page, section, the matched notation), and subtopics are ranked by how many equations need them. The text layer of a PDF writes mathematics loosely (superscripts and
Greek letters become plain characters), so the rules match both Unicode and plain spellings; a notation that is not recognised is simply not listed."""
import re

# (subtopic, subject, pattern over the equation text, why a reader needs it)
RULES = [
    ("Expectation of a random variable", "Probability", r"(?<![A-Za-z0-9])[Eᴼ\U0001d53c]\s*[_\[\(\{]|\U0001d53c|(?<![A-Za-z0-9])E\s*[A-Za-zτθπ](?:,\s*[A-Za-z]+)*\s*[∼~]|\bexpect(?:ed|ation)\b", "E[...] is an average over a distribution"),
    ("Sampling from a distribution (x ~ D)", "Probability", r"[∼~]\s*[A-Za-zπθ(ℒ\U0001d49f]", "the symbol ~ says a variable is drawn from a distribution"),
    ("Conditional probability", "Probability", r"[A-Za-zπθ][A-Za-zθ_0-9]*\s*\(\s*[A-Za-z][\w,\s']*\|\s*[A-Za-z][\w,\s'<]*\)", "p(a|b) is the probability of a given b"),
    ("Softmax and normalised exponentials", "Probability", r"softmax|\bexp\s*\(.*\)\s*/|\be\^[^/]{1,30}/\s*[∑Σ]", "softmax turns scores into probabilities"),
    ("Gaussian distribution", "Probability", r"\bN\s*\(\s*[μ0-9x]|\bGaussian\b|ℳ\s*\(", "N(mean, variance) is the normal distribution"),
    ("Variance and covariance", "Statistics", r"\bVar\b|\bCov\b|σ\s*2|σ²|\bvariance\b", "variance measures spread"),
    ("Kullback-Leibler divergence", "Information Theory", r"\bKL\b|\bD\s*_?\s*KL\b|\bDKL\b|\bKullback", "KL measures how one distribution differs from another"),
    ("Cross-entropy and log-likelihood", "Information Theory", r"[−\-]\s*(?:[E∑Σ]\S*\s*)?\[?\s*log\b|[−\-]\s*[∑Σ][^=]{0,30}\blog\b|\blog\s*p|\bNLL\b|cross[- ]entropy|log[- ]likelihood", "a negative log term is a cross-entropy / log-likelihood loss"),
    ("Logarithms and exponentials", "Calculus", r"\blog\s*[(\[{_]|\blog\s*[A-Za-zπθσ∑Σ](?![A-Za-z])|\bln\s*[(\[{A-Za-z]\b|\bexp\b|\be\^", "log and exp rules are needed to manipulate the expression"),
    ("Sigmoid and logistic functions", "Calculus", r"σ\s*\(|sigmoid|logistic", "sigma(x) squashes a value into (0, 1)"),
    ("Gradients and partial derivatives", "Calculus", r"[∇∂]|\bgrad\b", "the gradient is the vector of partial derivatives"),
    ("Integration", "Calculus", r"∫", "an integral sums a quantity over a continuous range"),
    ("Summation and product notation", "Calculus", r"[∑Σ∏Π]", "sums and products over an index"),
    ("Matrix multiplication and transpose", "Linear Algebra", r"QK|[A-Za-z\)\]]\s*⊤|\^\s*[T⊤]\b|\b[A-Za-z]{1,2}T\b\s*[/)]|\bX\s*W\b|\bW[A-Za-z_0-9]*\s*[xhXH]\b", "products and transposes of matrices (for example a query-key dot product)"),
    ("Vector norms and dot products", "Linear Algebra", r"‖|\|\|[^|]+\|\||\bnorm\b|√\s*d|\bsqrt\b", "norms and dot products measure length and similarity"),
    ("Optimisation objectives (argmin and argmax)", "Optimization", r"arg\s*(?:max|min)|\b(?:max|min)\s*[_⁡]", "the expression asks for the value that makes an objective largest or smallest"),
]
_COMPILED = [(topic, subject, re.compile(pattern, re.IGNORECASE if topic.startswith(("Softmax", "Kullback", "Cross", "Variance", "Gaussian")) else 0), why) for topic, subject, pattern, why in RULES]


def subtopics_of(expression):
    """[(subtopic, subject, matched text, why)] recognised in one equation's text, in rule order."""
    text = " ".join((expression or "").split())
    found = []
    for topic, subject, pattern, why in _COMPILED:
        match = pattern.search(text)
        if match:
            found.append((topic, subject, match.group(0).strip(), why))
    return found


def analyse(equations, resource_for=None):
    """Ranked [{subtopic, subject, why, equation_count, equations: [{equation_id, tag, page_number, section, matched, expression}], resource}] for a paper's equations. Ranked by
    the number of equations that need the subtopic, then by the earliest page, then by name; `resource` is the curated study link of the subject, or None."""
    if resource_for is None:
        from backend.resources.learning_resource_recommender import LearningResourceRecommender

        resource_for = LearningResourceRecommender.for_concept
    grouped = {}
    for equation in equations:
        for topic, subject, matched, why in subtopics_of(equation.expression):
            entry = grouped.setdefault(topic, {"subtopic": topic, "subject": subject, "why": why, "equations": []})
            entry["equations"].append({"equation_id": equation.equation_id, "tag": getattr(equation, "tag", ""), "page_number": getattr(equation, "page_number", None),
                                       "section": equation.section, "matched": matched, "expression": equation.expression[:200]})
    result = []
    for entry in grouped.values():
        link = resource_for(entry["subject"])
        entry["equation_count"] = len(entry["equations"])
        entry["resource"] = {"title": link[0], "provider": link[1], "url": link[2], "hours": link[3]} if link else None
        result.append(entry)
    return sorted(result, key=lambda e: (-e["equation_count"], min((q["page_number"] or 10**6) for q in e["equations"]), e["subtopic"]))
