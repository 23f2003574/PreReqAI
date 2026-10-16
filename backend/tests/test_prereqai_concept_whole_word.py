from types import SimpleNamespace

from backend.concepts import RuleBasedConceptDetector




def _counts(text):
    paper = SimpleNamespace(concepts=[], paragraphs=[SimpleNamespace(content=text, section_title="Intro")])
    RuleBasedConceptDetector().detect(paper)
    return {c.name: c.occurrences for c in paper.concepts}


def test_names_only_match_whole_words():
    assert "Attention" not in _counts("Inattention and attentional drift. Softmaxed scores.")
    assert "Softmax" not in _counts("Softmaxed scores.")


def test_plural_names_still_count():
    assert _counts("Transformers and residual connections.") == {"Transformer": 1, "Residual Connection": 1}


def test_longer_concept_not_double_counted_and_standalone_counts():
    assert _counts("Self-Attention helps. Attention is all.") == {"Self-Attention": 1, "Attention": 1}
