"""A URL that is not an arXiv or DOI link is refused as an unsupported source, not misread as a local file path."""
import pytest

from backend.ingestion.research_source_detector import ResearchSourceDetector
from backend.platform.prereqai_platform import PreReqAIPlatform

pytestmark = pytest.mark.prereqai


@pytest.mark.parametrize("url", ["https://example.com/paper.pdf", "http://host/a/b.PDF", "ftp://host/paper.pdf", "file:///tmp/paper.pdf"])
def test_other_urls_are_unsupported_sources(url):
    with pytest.raises(ValueError, match="Unsupported research source"):
        ResearchSourceDetector().detect(url)


def test_the_user_is_told_to_give_an_arxiv_link_or_doi_not_that_a_file_is_missing():
    outcome = PreReqAIPlatform().analyze("https://example.com/paper.pdf")
    assert outcome["status"] == "failure"
    assert "no such file" not in outcome["detail"] and "arXiv" in outcome["hint"]


def test_valid_sources_are_unchanged(tmp_path):
    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    detect = ResearchSourceDetector().detect
    assert detect(str(pdf)).source_type == "pdf"
    assert detect("missing/paper.pdf").source_type == "pdf"   # a not-yet-existing local path still reports "no such file" later
    assert detect("https://arxiv.org/abs/1706.03762").source_type == "arxiv"
    assert detect("https://doi.org/10.1145/3292500.3330701").source_type == "doi"
