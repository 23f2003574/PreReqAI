"""Old-style arXiv identifiers (hep-th/9901001) and links with a query string or the export mirror are accepted."""
import pytest

from backend.ingestion.arxiv_resolver import ArxivResolver
from backend.ingestion.research_source_detector import ResearchSourceDetector


@pytest.mark.parametrize("text, identifier", [
    ("arXiv:hep-th/9901001", "hep-th/9901001"),
    ("https://arxiv.org/abs/hep-th/9901001v2", "hep-th/9901001v2"),
    ("https://arxiv.org/pdf/math.GT/0309136.pdf", "math.GT/0309136"),
    ("https://arxiv.org/abs/1706.03762?context=cs", "1706.03762"),
    ("arxiv.org/abs/1706.03762#section", "1706.03762"),
    ("http://export.arxiv.org/abs/1706.03762", "1706.03762"),
])
def test_these_references_are_arxiv_papers(text, identifier):
    source = ResearchSourceDetector().detect(text)
    assert (source.source_type, source.identifier) == ("arxiv", identifier)


@pytest.mark.parametrize("text", ["hep-th/9901001", "1706.03762", "https://arxiv.org/abs/hep-th/99010",
                                  "https://arxiv.org/abs/1706.03762 and more text"])
def test_ambiguous_or_malformed_references_are_still_rejected(text):
    with pytest.raises(ValueError, match="Unsupported research source"):
        ResearchSourceDetector().detect(text)


def test_an_old_style_id_is_downloaded_from_its_pdf_url_and_cached_in_one_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ArxivResolver, "CACHE_DIRECTORY", tmp_path / "arxiv")
    urls = []
    monkeypatch.setattr(ArxivResolver, "_download", lambda self, url: urls.append(url) or b"%PDF-1.4 x")
    resolver, source = ArxivResolver(), ResearchSourceDetector().detect("arXiv:hep-th/9901001")

    path = resolver.resolve(source)

    assert urls == ["https://arxiv.org/pdf/hep-th/9901001.pdf"]
    assert path == str(tmp_path / "arxiv" / "hep-th_9901001.pdf") and open(path, "rb").read().startswith(b"%PDF")
    assert resolver.resolve(source) == path and len(urls) == 1  # the second resolve is served from the cache
