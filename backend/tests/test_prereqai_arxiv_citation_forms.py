"""An arXiv paper can be given the way it is usually cited, not only as a full URL."""
import pytest

from backend.ingestion.research_source_detector import ResearchSourceDetector


@pytest.mark.parametrize("given, identifier", [
    ("arXiv:1706.03762", "1706.03762"),
    ("arxiv: 1706.03762v5", "1706.03762v5"),
    ("https://arxiv.org/abs/1706.03762", "1706.03762"),
])
def test_citation_forms_are_detected_as_arxiv(given, identifier):
    source = ResearchSourceDetector().detect(given)
    assert (source.source_type, source.identifier) == ("arxiv", identifier)


def test_www_doi_org_links_are_detected_as_doi():
    assert ResearchSourceDetector().detect("https://www.doi.org/10.1000/xyz").source_type == "doi"


@pytest.mark.parametrize("given", ["1706.03762", "3.14", "notes.txt", "arxiv:abc", "see arXiv:1706.03762 here"])
def test_ordinary_text_is_still_rejected(given):
    with pytest.raises(ValueError, match="Unsupported research source"):
        ResearchSourceDetector().detect(given)


