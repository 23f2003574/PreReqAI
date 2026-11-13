"""Prerequisite subjects are counted from the paper's own terms: most (Linear Algebra, Calculus...) are not registry concepts."""
import pytest

from backend.concepts.rule_based_concept_detector import subject_mentions
from backend.models import Paper, Paragraph, Prerequisite
from backend.prerequisites import MissingPrerequisiteAnalyzer

pytestmark = pytest.mark.prereqai


def counts(*paragraphs):
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.paragraphs = [Paragraph(i, title, text) for i, (title, text) in enumerate(paragraphs, 1)]
    return subject_mentions(paper)


@pytest.mark.parametrize("subject, text", [
    ("Linear Algebra", "We use eigenvalues and matrix multiplication."),
    ("Probability", "A random variable has a conditional probability; Bayes' rule applies."),
    ("Calculus", "The partial derivative follows the chain rule."),
    ("Information Theory", "The KL divergence and Shannon entropy are used."),
    ("Neural Networks", "A multilayer perceptron is a neural network."),
    ("Graphs", "A directed graph has an adjacency matrix."),
    ("Attention", "The attention mechanism uses self-attention."),
    ("Transformer", "The transformer is a model."),
    ("Markov Decision Process", "A Markov decision process, or MDP, models the task."),
    ("Optimization", "A convex optimization problem has no bad local minima."),
    ("Statistics", "Statistical inference gives a confidence interval."),
    ("Stochastic Processes", "A Markov chain is a stochastic process; so is Brownian motion."),
])
def test_every_subject_is_detected_by_its_own_terms(subject, text):
    found = counts(("Method", text))
    assert found[subject] >= 2 or subject in ("Transformer",) and found[subject] == 1
    assert all(count == 0 for name, count in found.items() if name != subject and subject in ("Calculus", "Graphs", "Markov Decision Process"))


def test_all_nine_subjects_are_reported_even_when_absent():
    assert counts(("Method", "Nothing relevant here.")) == dict.fromkeys(
        ["Linear Algebra", "Probability", "Calculus", "Information Theory", "Neural Networks", "Graphs", "Attention", "Transformer",
         "Markov Decision Process", "Optimization", "Statistics", "Stochastic Processes"], 0)


def test_aliases_hyphenation_and_repeats_are_counted():
    found = counts(("Method", "Multi-head attention, multi head attention and MDPs.\nThe multi-\nhead attention mechanism. An MDP. MDP."))
    assert found["Attention"] == 3 and found["Markov Decision Process"] == 3


def test_overlapping_terms_count_once_and_cross_entropy_is_not_information_theory():
    found = counts(("Method", "Cross-entropy loss and cross entropy. Entropy is high."))
    assert found["Information Theory"] == 1


def test_ordinary_language_is_not_counted():
    found = counts(("Method", "The graph shows the loss. This is probably a high probability of failure. Pay attention to the derivative "
                              "market; a gradient colour. Transformation of data."))
    assert not any(found.values())


def test_bibliography_titles_are_not_counted():
    found = counts(("Method", "A calculus of variations."), ("References", "[1] Calculus. [2] Calculus Made Easy, calculus."))
    assert found["Calculus"] == 1


def analyse(paper, *subjects):
    paper.prerequisites = [Prerequisite(concept=name, reason="Required", confidence=1.0) for name in subjects]
    return {m.concept: m for m in MissingPrerequisiteAnalyzer().analyze(paper).missing_prerequisites}


def test_a_subject_without_registry_entry_is_judged_on_its_own_mentions():
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.paragraphs = [Paragraph(1, "Background", "Calculus matters. The chain rule, a partial derivative."),
                        Paragraph(2, "Method", "Linear algebra once.")]
    result = analyse(paper, "Calculus", "Linear Algebra", "Probability")
    assert (result["Calculus"].status, result["Calculus"].mentions, result["Calculus"].satisfied) == ("covered", 3, True)
    assert (result["Linear Algebra"].status, result["Linear Algebra"].mentions) == ("mentioned_only", 1)
    assert (result["Probability"].status, result["Probability"].mentions) == ("not_mentioned", 0)


def test_a_registry_concept_keeps_its_detected_count():
    from backend.models import DetectedConcept

    paper = Paper(source_path="p.pdf", metadata=None)
    paper.concepts.append(DetectedConcept(name="Attention", domain="transformers", occurrences=2))
    paper.paragraphs = [Paragraph(1, "Method", "Self-attention, attention mechanism, attention heads, attention layers.")]
    assert analyse(paper, "Attention")["Attention"].mentions == 2


def test_dot_product_attention_is_not_a_linear_algebra_mention():
    found = counts(("Method", "Scaled dot-product attention uses a dot product."))
    assert found["Linear Algebra"] == 0 and found["Attention"] == 1
