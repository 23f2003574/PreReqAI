"""An arXiv HTML link (https://arxiv.org/html/<id>) names the same paper as its abs/pdf link, so it is accepted."""
import pytest

from backend.ingestion.research_source_detector import ResearchSourceDetector

pytestmark = pytest.mark.prereqai


@pytest.mark.parametrize("link, identifier", [
    ("https://arxiv.org/html/1706.03762", "1706.03762"),
    ("https://arxiv.org/html/1706.03762v7", "1706.03762v7"),
    ("arxiv.org/html/hep-th/9901001/?utm=x", "hep-th/9901001"),
])
def test_html_links_resolve_to_the_arxiv_identifier(link, identifier):
    source = ResearchSourceDetector().detect(link)
    assert (source.source_type, source.identifier) == ("arxiv", identifier)


@pytest.mark.parametrize("link", [
    "https://arxiv.org/html/",                      # no identifier
    "https://arxiv.org/html/not-an-id",
])
def test_html_look_alikes_are_still_rejected(link):
    with pytest.raises(ValueError):
        ResearchSourceDetector().detect(link)


def test_another_site_is_not_read_as_arxiv_but_as_a_direct_link_that_must_prove_to_be_a_pdf():
    source = ResearchSourceDetector().detect("https://alphaxiv.org/html/1706.03762")
    assert source.source_type == "pdf_url"  # never the arXiv id; the download is accepted only if its content is a PDF
