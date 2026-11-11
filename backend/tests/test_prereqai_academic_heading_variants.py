import pytest

from backend.ingestion.document_metadata_extractor import DocumentMetadata
from backend.ingestion.pdf_ingestion_engine import RawDocument, RawPage
from backend.parsing import ScientificSectionParser


def _sections(text):
    document = RawDocument("p.pdf", DocumentMetadata("t", "a", "", "", "", "", 1), [RawPage(1, text)])
    return [(s.title, s.content) for s in ScientificSectionParser().parse(document).sections]


@pytest.mark.parametrize("heading", [
    "Experimental Evaluation", "Empirical Evaluation", "Discussion and Limitations", "Limitations and Discussion",
    "Concluding Remarks", "Concluding Remarks and Future Work", "5 Experimental Evaluation", "concluding remarks",
])
def test_academic_heading_variants_start_their_own_section(heading):
    assert _sections(f"1 Introduction\nIntro text.\n{heading}\nBody of it.\n") == [("1 Introduction", "Intro text."), (heading, "Body of it.")]


@pytest.mark.parametrize("line", [
    "The experimental evaluation shows gains.", "Concluding remarks are given below.", "Discussion and limitations are in Section 6.",
])
def test_sentences_with_the_same_words_stay_body_text(line):
    assert _sections(f"1 Introduction\n{line}\n") == [("1 Introduction", line)]


def test_nearby_recognised_headings_stay_distinct():
    text = "Experimental Setup\nA.\nExperimental Evaluation\nB.\nDiscussion\nC.\nDiscussion and Limitations\nD.\nConclusion\nE.\n"
    assert [t for t, _ in _sections(text)] == ["Experimental Setup", "Experimental Evaluation", "Discussion", "Discussion and Limitations", "Conclusion"]
