"""A reference pasted out of text (angle brackets, trailing full stop, scheme-less doi.org, 'DOI ' prefix) is recognised;
real unsupported input is still rejected and an existing local file is never rewritten."""
import pytest

from backend.ingestion.research_source_detector import ResearchSourceDetector

pytestmark = pytest.mark.prereqai

ARXIV = "1706.03762"
DOI = "10.1145/3292500.3330701"


@pytest.mark.parametrize("text, kind, identifier", [
    ("<https://arxiv.org/abs/1706.03762>", "arxiv", ARXIV),
    ("(arXiv:1706.03762).", "arxiv", ARXIV),
    ('"arxiv.org/abs/1706.03762v5",', "arxiv", "1706.03762v5"),
    ("https://doi.org/10.1145/3292500.3330701.", "doi", DOI),
    ("DOI 10.1145/3292500.3330701", "doi", DOI),
    ("doi: 10.1145/3292500.3330701;", "doi", DOI),
    ("dx.doi.org/10.1145/3292500.3330701", "doi", DOI),
    ("doi.org/10.1145/3292500.3330701", "doi", DOI),
])
def test_pasted_references_are_recognised(text, kind, identifier):
    found = ResearchSourceDetector().detect(text)
    assert (found.source_type, found.identifier) == (kind, identifier)


@pytest.mark.parametrize("text", ["<https://example.com/paper.pdf>", "notes.txt.", "see arXiv:1706.03762 for details", "1706.03762"])
def test_other_input_is_still_rejected(text):
    with pytest.raises(ValueError):
        ResearchSourceDetector().detect(text)


def test_an_existing_local_pdf_is_still_a_local_pdf(tmp_path):
    pdf = tmp_path / "paper, v2.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    found = ResearchSourceDetector().detect(str(pdf))
    assert (found.source_type, found.identifier) == ("pdf", str(pdf))
