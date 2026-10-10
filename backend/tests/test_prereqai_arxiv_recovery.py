"""A transient arXiv failure (dropped connection, 503) is retried a bounded number of times; a permanent
one (404) or a still-failing service surfaces unchanged, and nothing bad is cached."""
import pytest
import requests

from backend.ingestion.arxiv_resolver import ArxivResolver
from backend.ingestion.research_source_detector import ResearchSource

PDF = b"%PDF-1.4 minimal"


class _Reply:
    def __init__(self, status=200, content=PDF):
        self.status_code, self.content = status, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code}", response=self)


@pytest.fixture
def resolver(tmp_path, monkeypatch):
    monkeypatch.setattr(ArxivResolver, "CACHE_DIRECTORY", tmp_path / "arxiv")
    monkeypatch.setattr(ArxivResolver, "RETRY_DELAYS", (0, 0))
    return ArxivResolver()


def _script(monkeypatch, *steps):
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        step = steps[min(len(calls), len(steps)) - 1]
        if isinstance(step, Exception):
            raise step
        return step

    monkeypatch.setattr(requests, "get", fake_get)
    return calls


SOURCE = ResearchSource(source_type="arxiv", identifier="1706.03762", original_input="1706.03762")


def test_a_dropped_connection_then_a_busy_server_then_success_downloads_the_paper(resolver, monkeypatch):
    calls = _script(monkeypatch, requests.exceptions.ConnectionError("reset"), _Reply(503), _Reply())

    path = resolver.resolve(SOURCE)

    assert len(calls) == 3 and open(path, "rb").read() == PDF


def test_a_missing_paper_is_not_retried(resolver, monkeypatch):
    calls = _script(monkeypatch, _Reply(404))

    with pytest.raises(requests.exceptions.HTTPError):
        resolver.resolve(SOURCE)

    assert len(calls) == 1


def test_a_service_that_keeps_failing_surfaces_the_original_error_after_bounded_attempts(resolver, monkeypatch):
    calls = _script(monkeypatch, _Reply(503))

    with pytest.raises(requests.exceptions.HTTPError, match="503"):
        resolver.resolve(SOURCE)

    assert len(calls) == 3  # one try plus the two configured retries
    assert not list(resolver.CACHE_DIRECTORY.glob("*"))  # nothing half-written was cached
