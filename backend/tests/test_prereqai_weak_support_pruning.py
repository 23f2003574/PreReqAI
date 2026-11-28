"""A prerequisite implied only by a concept the paper mentions once is reported as weak support, not recommended; central concepts keep theirs. Real-paper labels are AI-written and PROVISIONAL."""
from types import SimpleNamespace

import pytest

from backend.models import Paper
from backend.models.paper import DetectedConcept, DocumentMetadata, Paragraph
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

pytestmark = pytest.mark.prereqai
FILLER = "The study reports its method and results in plain words. " * 220


def _paper(concepts):
    paper = Paper(source_path="x.pdf", metadata=DocumentMetadata(title="T", author="A", subject="", keywords="", creator="", producer="", page_count=1))
    paper.paragraphs = [Paragraph(1, "2 Method", FILLER)]
    paper.concepts = [DetectedConcept(name=n, domain="x", occurrences=k) for n, k in concepts]
    return paper


def test_one_mention_of_transformer_no_longer_implies_attention_in_a_full_paper():
    paper = PrerequisiteDetector().detect(_paper([("Transformer", 1), ("Neural Networks", 9)]))
    names = {p.concept for p in paper.prerequisites}
    assert "Attention" not in names and {w["concept"] for w in paper.weak_prerequisites} >= {"Attention"}


def test_a_central_concept_still_brings_its_prerequisite():
    paper = PrerequisiteDetector().detect(_paper([("Transformer", 12), ("Neural Networks", 9)]))
    assert "Attention" in {p.concept for p in paper.prerequisites} and not any(w["concept"] == "Attention" for w in paper.weak_prerequisites)


def test_a_short_text_keeps_every_inferred_prerequisite():
    paper = _paper([("Transformer", 1)])
    paper.paragraphs = [Paragraph(1, "Body", "A Transformer is used.")]
    assert "Attention" in {p.concept for p in PrerequisiteDetector().detect(paper).prerequisites}


def test_real_paper_precision_improves_with_recall_held():
    from backend.prereqai_eval import gate, prerequisite_eval

    data = prerequisite_eval.load()
    report = prerequisite_eval.evaluate(gate._real_papers(set(data["papers"])), data)
    assert report["precision"] >= 0.436 + 0.04 and report["recall"] >= 0.459 + 0.2 and "Attention" not in report["papers"]["dpo"]["false_positives"] and "Transformer" not in report["papers"]["dpo"]["false_positives"]
