"""Concept detection scans the paper text only for registry terms the paper actually contains."""
import re

import backend.concepts.rule_based_concept_detector as detector_module
from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.models import Paper, Paragraph


def _paper(text):
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.paragraphs.append(Paragraph(paragraph_id=1, section_title="Body", content=text))
    return paper


def _naive_counts(detector, text):
    """The straightforward definition the optimisation must not change: a whole-word regex scan per term."""
    text = re.sub(r"\s+", " ", text.lower())
    return {c.name: len(re.findall(rf"\b{re.escape(c.name.lower())}s?\b", text)) for c in detector.registry.all()}


def test_absent_terms_are_rejected_without_a_regex_scan(monkeypatch):
    calls = []
    real = re.findall
    monkeypatch.setattr(detector_module.re, "findall", lambda pattern, string, *a: calls.append(pattern) or real(pattern, string, *a))
    detector = RuleBasedConceptDetector()
    terms = sum(1 + len(c.aliases) for c in detector.registry.all())

    paper = detector.detect(_paper("Softmax turns scores into probabilities. " * 50))

    assert [c.name for c in paper.concepts] == ["Softmax"]
    assert 0 < len(calls) < terms // 4  # only the terms found in the text (and their longer concepts) were scanned


def test_counts_match_a_plain_regex_scan_including_plurals_and_substrings():
    detector = RuleBasedConceptDetector()
    text = ("Softmax and softmaxes; inattention is not attention. Self-attention and multi-head attention differ. "
            "A policy gradient, two policy gradients, a transformer and transformers.")
    found = {c.name: c.occurrences for c in detector.detect(_paper(text)).concepts}
    expected = _naive_counts(detector, text)
    assert found["Softmax"] == expected["Softmax"] == 1  # "softmaxes" is not a plain plural
    assert found["Transformer"] == expected["Transformer"] == 2
    assert found["Policy Gradient"] == expected["Policy Gradient"] == 2
    assert found["Attention"] == 1  # only the standalone word: not "inattention", self-attention or multi-head attention
