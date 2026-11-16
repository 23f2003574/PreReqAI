"""Ambiguous everyday-word concepts (attention, dropout, embedding, overfitting) count only in technical context."""
import pytest

from backend.concepts import ConceptRegistry, RuleBasedConceptDetector
from backend.concepts.rule_based_concept_detector import section_mentions
from backend.models import Paper, Paragraph
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

pytestmark = pytest.mark.prereqai


def _paper(*parts):
    paper = Paper(source_path="x.pdf", metadata=None)
    paper.paragraphs = [Paragraph(i, title, text) for i, (title, text) in enumerate(parts, start=1)]
    return paper


def _found(text):
    paper = RuleBasedConceptDetector().detect(_paper(("Body", text)))
    return {c.name: c.occurrences for c in paper.concepts}


@pytest.mark.parametrize("text", [
    "Please pay attention to detail.",
    "Dropout rates rose at the school last year.",
    "The embedding of the stone in the wall was careful.",
    "The tailor overfit the jacket.",
    "Students pay attention; dropout rates rose; a stone embedding was found.",  # the everyday words cannot vouch for each other
])
def test_everyday_uses_are_not_concepts(text):
    assert _found(text) == {}


@pytest.mark.parametrize("text, name", [
    ("We apply dropout to the hidden layers.", "Dropout"),  # short, technical by its own phrase
    ("Dropout of 0.1 is used.", "Dropout"),
    ("Attention weights are computed with a softmax.", "Attention"),
    ("The attention mechanism helps.", "Attention"),
    ("Word embeddings are learned.", "Embedding"),
    ("The embedding is a vector looked up per token.", "Embedding"),  # bare word, corroborated by vector and token
    ("A larger model can overfit the training data.", "Overfitting"),
    ("Regularisation reduces overfitting.", "Overfitting"),
])
def test_technical_uses_keep_detection(text, name):
    assert name in _found(text)


def test_counts_are_kept_and_deterministic():
    text = "Attention is computed per head. Attention weights sum to one. A transformer stacks attention layers with a softmax."
    first = _found(text)
    assert first["Attention"] == 3 and first == _found(text)


def test_longer_concepts_still_shadow_the_bare_word():
    found = _found("Self-attention and multi-head attention are used in the transformer.")
    assert found["Self-Attention"] == 1 and "Attention" not in found


def test_section_attribution_uses_the_whole_paper_as_evidence():
    paper = _paper(("Method", "We use dropout and embedding tables in the neural network."), ("Experiments", "Dropout was tuned."))
    found = section_mentions(paper)
    assert found["Experiments"]["concepts"]["Dropout"] == 1  # the section is judged by its paper's technical evidence
    unrelated = _paper(("Intro", "Dropout rates rose."), ("Other", "Pay attention to detail."))
    assert section_mentions(unrelated) == {}


def test_ambiguous_flags_are_declared_in_the_registry():
    ambiguous = {c.name for c in ConceptRegistry().all() if c.ambiguous}
    assert ambiguous == {"Attention", "Dropout", "Embedding", "Overfitting"}
    assert all(c.technical and c.context for c in ConceptRegistry().all() if c.ambiguous)


def test_a_false_positive_no_longer_creates_prerequisites():
    paper = RuleBasedConceptDetector().detect(_paper(("Body", "Pay attention to detail; dropout rates rose.")))
    assert PrerequisiteDetector().detect(paper).prerequisites == []
    real = RuleBasedConceptDetector().detect(_paper(("Body", "The attention mechanism uses softmax over query and key vectors.")))
    assert {p.concept for p in PrerequisiteDetector().detect(real).prerequisites} >= {"Linear Algebra", "Probability"}
