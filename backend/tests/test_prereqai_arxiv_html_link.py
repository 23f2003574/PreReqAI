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
    "https://alphaxiv.org/html/1706.03762",         # another site
])
def test_html_look_alikes_are_still_rejected(link):
    with pytest.raises(ValueError):
        ResearchSourceDetector().detect(link)
