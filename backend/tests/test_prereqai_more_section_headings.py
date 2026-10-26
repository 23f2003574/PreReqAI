"""Unnumbered headings that real ML papers use (Notation, Datasets, Implementation Details, ...) start their own section."""
from types import SimpleNamespace

from backend.parsing.scientific_section_parser import ScientificSectionParser


def _titles(text):
    document = SimpleNamespace(full_text=text, source_path="p.pdf", metadata=None, pages=[])
    return [section.title for section in ScientificSectionParser().parse(document).sections]


def test_common_unnumbered_ml_paper_headings_are_sections():
    text = ("Introduction\nWe study attention.\nNotation\nLet x be a token.\nDatasets\nWMT.\nImplementation Details\nAdam.\n"
            "Training Procedure\nSteps.\nTheoretical Analysis\nBound.\nProofs\nQED.\nReproducibility Statement\nCode.\n")
    assert _titles(text) == ["Introduction", "Notation", "Datasets", "Implementation Details", "Training Procedure",
                             "Theoretical Analysis", "Proofs", "Reproducibility Statement"]


def test_these_words_inside_sentences_are_not_headings():
    text = "Introduction\nTraining is slow.\nThe Datasets were large.\nTheory suggests otherwise.\n"
    assert _titles(text) == ["Introduction"]
