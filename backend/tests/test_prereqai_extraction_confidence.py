"""Extraction confidence: measured signals, specific actionable warnings for poor input, none for good input, and the report, API, CLI and page carrying it."""
from types import SimpleNamespace

import pytest

from backend import extraction_confidence as confidence
from backend.models import Citation, DetectedConcept, Paper, PaperReference, PaperSection, Paragraph

pytestmark = pytest.mark.prereqai
LONG = "The Transformer computes attention over the tokens of the sequence. " * 6


def page(n, text=LONG * 2, **extra):
    return SimpleNamespace(**{"page_number": n, "text": text, "ocr": False, "ocr_error": "", "ocr_stopped": False, "ocr_quality": None, **extra})


def good():
    paper = Paper(source_path="g.pdf", metadata=None)
    paper.pages = [page(1), page(2), page(3)]
    paper.sections = [PaperSection(title=t, content="x") for t in ("Abstract", "1 Introduction", "2 Method", "3 Results", "References")]
    paper.references = [PaperReference(i, f"Author {i}. A title. 2020.") for i in range(1, 8)]
    paper.citations = [Citation(i, i, "see [x]", "1 Introduction") for i in range(1, 6)]
    paper.paragraphs = [Paragraph(i, "1 Introduction", LONG, 1) for i in range(1, 8)]
    paper.concepts = [DetectedConcept(name="Attention", domain="transformers", occurrences=3)]
    return paper


def signals(result):
    return {s["name"]: s["status"] for s in result["signals"]}


def test_a_well_extracted_paper_is_high_with_no_warnings_and_seven_measured_signals():
    result = confidence.assess(good())
    assert result["level"] == "high" and result["warnings"] == [] and len(result["signals"]) == 7 and set(signals(result).values()) == {"ok"}
    assert confidence.warning_lines(result) == [] and result["note"] == "No extraction problem was found."


def test_each_kind_of_poor_input_gets_its_own_specific_actionable_warning():
    scan = good()
    scan.pages = [page(n, text="") for n in (1, 2, 3)]
    result = confidence.assess(scan)
    assert result["level"] == "low" and signals(result)["text_layer"] == "poor" and any("scan" in w["message"] and w["action"] for w in result["warnings"])
    assert any(line.startswith("Extraction confidence is low:") for line in confidence.warning_lines(result))
    flat = good()
    flat.sections, flat.paragraphs = [], [Paragraph(1, "x", "word " * 1000, 1)]
    flat_result = confidence.assess(flat)
    assert signals(flat_result)["headings"] == "poor" and signals(flat_result)["layout"] == "warn" and confidence.warning_lines(flat_result) == []  # structure problems are reported, not run warnings
    partial = good()
    partial.pages = [page(1, ocr=True, ocr_quality=0.9), page(2, text="", ocr=False, ocr_error="the OCR limit of 1 pages was reached", ocr_stopped=True), page(3)]
    partial_result = confidence.assess(partial)
    assert signals(partial_result)["ocr"] == "warn" and "partial" in next(w for w in partial_result["warnings"] if w["signal"] == "ocr")["message"]


def test_ocr_quality_comes_from_the_recognition_score_and_unreadable_scans_are_poor():
    noisy = good()
    noisy.pages = [page(1, ocr=True, ocr_quality=0.62), page(2), page(3)]
    assert signals(confidence.assess(noisy))["ocr"] == "warn" and "0.62" in next(s for s in confidence.assess(noisy)["signals"] if s["name"] == "ocr")["detail"]
    unreadable = good()
    unreadable.pages = [page(1, text="", ocr_error="the recognised text was too noisy to trust (quality 0.41)"), page(2), page(3)]
    result = confidence.assess(unreadable)
    assert signals(result)["ocr"] == "poor" and "too noisy" in next(w for w in result["warnings"] if w["signal"] == "ocr")["message"]
    assert any("too noisy" in line for line in confidence.warning_lines(result))


def test_missing_references_unresolved_citations_duplicate_headings_and_no_concepts_are_warnings():
    paper = good()
    paper.references, paper.concepts = [], []
    paper.citations = [Citation(i, 99, "see [x]", "1 Introduction") for i in range(1, 5)]
    paper.sections.append(PaperSection(title="2 Method", content="y"))
    result = confidence.assess(paper)
    assert result["level"] == "medium" and {s: v for s, v in signals(result).items() if v != "ok"} == {"headings": "warn", "references": "warn", "citations": "warn", "concepts": "warn"}
    assert next(w for w in result["warnings"] if w["signal"] == "headings")["message"].endswith("appears more than once.")
    assert "confirm the ones you need" in next(w for w in result["warnings"] if w["signal"] == "concepts")["action"]


def test_an_empty_paper_is_low_without_crashing():
    result = confidence.assess(Paper(source_path="e.pdf", metadata=None))
    assert result["level"] == "low" and signals(result)["text_layer"] == "poor" and signals(result)["layout"] == "poor"
