"""A damaged cached download (empty, an HTML error page) is replaced by a fresh download instead of being reused forever;
a good cached PDF is still reused without any network request."""
import pytest
import requests

from backend.ingestion.arxiv_resolver import ArxivResolver
from backend.ingestion.research_source_detector import ResearchSource

pytestmark = pytest.mark.prereqai

PDF = b"%PDF-1.4 fresh"


class _Reply:
    status_code = 200
    content = PDF

    def raise_for_status(self):
        pass


@pytest.fixture
def resolver(tmp_path, monkeypatch):
    monkeypatch.setattr(ArxivResolver, "CACHE_DIRECTORY", tmp_path / "arxiv")
    monkeypatch.setattr(ArxivResolver, "RETRY_DELAYS", ())
    calls = []
    monkeypatch.setattr(requests, "get", lambda url, timeout: calls.append(url) or _Reply())
    return ArxivResolver(), calls


SOURCE = ResearchSource(source_type="arxiv", identifier="1706.03762", original_input="arXiv:1706.03762")


@pytest.mark.parametrize("damaged", [b"", b"<html>503 Service Unavailable</html>"])
def test_a_damaged_cached_file_is_downloaded_again(resolver, damaged):
    resolve, calls = resolver
    ArxivResolver.CACHE_DIRECTORY.mkdir(parents=True)
    (ArxivResolver.CACHE_DIRECTORY / "1706.03762.pdf").write_bytes(damaged)

    path = resolve.resolve(SOURCE)

    assert len(calls) == 1
    assert open(path, "rb").read() == PDF


def test_a_good_cached_pdf_is_reused_without_a_request(resolver):
    resolve, calls = resolver
    ArxivResolver.CACHE_DIRECTORY.mkdir(parents=True)
    (ArxivResolver.CACHE_DIRECTORY / "1706.03762.pdf").write_bytes(b"%PDF-1.4 cached")

    assert open(resolve.resolve(SOURCE), "rb").read() == b"%PDF-1.4 cached"
    assert calls == []
