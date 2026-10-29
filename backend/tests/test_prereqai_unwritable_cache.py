"""A downloaded paper is analysed even when the working directory cannot hold the cache (read-only or unusual current
directory); it is cached in the temp directory instead and reused from there."""
import pytest
import requests

from backend.ingestion.arxiv_resolver import ArxivResolver
from backend.ingestion.doi_resolver import DoiResolver
from backend.ingestion.research_source_detector import ResearchSource

pytestmark = pytest.mark.prereqai

PDF = b"%PDF-1.4 fresh"


class _Reply:
    status_code = 200
    content = PDF

    def raise_for_status(self):
        pass


@pytest.fixture
def downloads(tmp_path, monkeypatch):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("a file where the cache directory should be")  # mkdir under a file fails like a read-only directory
    monkeypatch.setattr(ArxivResolver, "CACHE_DIRECTORY", blocker / "arxiv")
    monkeypatch.setattr(DoiResolver, "CACHE_DIRECTORY", blocker / "doi")
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path / "tmp"))
    calls = []
    monkeypatch.setattr(requests, "get", lambda url, timeout: calls.append(url) or _Reply())
    return calls


def test_an_unwritable_cache_falls_back_to_the_temp_directory_and_is_reused(downloads, tmp_path):
    source = ResearchSource(source_type="arxiv", identifier="1706.03762", original_input="arXiv:1706.03762")

    first = ArxivResolver().resolve(source)
    assert first.startswith(str(tmp_path / "tmp")) and open(first, "rb").read() == PDF
    assert ArxivResolver().resolve(source) == first
    assert len(downloads) == 1  # the second analysis used the cached copy


def test_a_writable_cache_is_still_used_first(tmp_path, monkeypatch):
    monkeypatch.setattr(ArxivResolver, "CACHE_DIRECTORY", tmp_path / "cache" / "arxiv")
    monkeypatch.setattr(requests, "get", lambda url, timeout: _Reply())
    source = ResearchSource(source_type="arxiv", identifier="1706.03762", original_input="arXiv:1706.03762")

    assert ArxivResolver().resolve(source) == str(tmp_path / "cache" / "arxiv" / "1706.03762.pdf")
