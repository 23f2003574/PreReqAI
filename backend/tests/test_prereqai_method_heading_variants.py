import pytest

from backend.ingestion.document_metadata_extractor import DocumentMetadata
from backend.ingestion.pdf_ingestion_engine import RawDocument, RawPage
from backend.parsing import ScientificSectionParser

HEADINGS = ["Materials and Methods", "Methods and Materials", "Proposed Method", "Proposed Approach", "Our Approach", "Network Architecture", "Evaluation Results", "3 Proposed Method"]


def _sections(text):
    document = RawDocument("p.pdf", DocumentMetadata("t", "a", "", "", "", "", 1), [RawPage(1, text)])
    return [(s.title, s.content) for s in ScientificSectionParser().parse(document).sections]


@pytest.mark.parametrize("heading", HEADINGS)
def test_method_and_evaluation_heading_variants_start_their_own_section(heading):
    assert _sections(f"1 Introduction\nIntro text.\n{heading}\nBody of it.\n") == [("1 Introduction", "Intro text."), (heading, "Body of it.")]


@pytest.mark.parametrize("line", ["Our approach is simple and fast.", "The proposed method works.", "Materials and methods are listed in Table 1."])
def test_sentences_with_the_same_words_stay_body_text(line):
    assert _sections(f"1 Introduction\n{line}\n") == [("1 Introduction", line)]


def test_existing_neighbouring_headings_are_unaffected():
    text = "Method\nA.\nProposed Method\nB.\nResults\nC.\nEvaluation Results\nD.\n"
    assert [t for t, _ in _sections(text)] == ["Method", "Proposed Method", "Results", "Evaluation Results"]
