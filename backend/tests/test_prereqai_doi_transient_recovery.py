"""A DOI download survives a transient failure (dropped connection, 503) like an arXiv download does; a permanent error
(404) is not retried and a persistent outage still surfaces."""
import pytest
import requests

from backend.ingestion import ResearchSource
from backend.ingestion.doi_resolver import DoiResolver

pytestmark = pytest.mark.prereqai

SOURCE = ResearchSource(source_type="doi", identifier="10.1234/abc", original_input="10.1234/abc")
PDF_URL = "https://example.org/p.pdf"


class Reply:
    is_redirect = False

    def __init__(self, status=200, payload=None, content=b""):
        self.status, self._payload, self.content = status, payload, content

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.exceptions.HTTPError(response=self)

    @property
    def status_code(self):
        return self.status

    def json(self):
        return self._payload


def _network(monkeypatch, tmp_path, script):
    """`script` maps 'crossref' / 'pdf' to a list of outcomes (an exception or a Reply) consumed in order."""
    monkeypatch.setattr(DoiResolver, "CACHE_DIRECTORY", tmp_path / "doi")
    monkeypatch.setattr(DoiResolver, "RETRY_DELAYS", (0, 0))
    monkeypatch.setattr("backend.ingestion.doi_resolver.is_public_https_url", lambda url: True)
    calls = {"crossref": 0, "pdf": 0}

    def get(url, **kwargs):
        kind = "pdf" if url == PDF_URL else "crossref"
        outcome = script[kind][min(calls[kind], len(script[kind]) - 1)]
        calls[kind] += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(requests, "get", get)
    return calls


GOOD_LINKS = Reply(payload={"message": {"link": [{"URL": PDF_URL, "content-type": "application/pdf"}]}})
GOOD_PDF = Reply(content=b"%PDF-1.4 ok\n%%EOF")


def test_transient_failures_on_both_requests_are_retried(monkeypatch, tmp_path):
    calls = _network(monkeypatch, tmp_path, {
        "crossref": [requests.exceptions.ConnectionError(), GOOD_LINKS],
        "pdf": [Reply(503), GOOD_PDF],
    })
    path = DoiResolver().resolve(SOURCE)
    assert open(path, "rb").read() == b"%PDF-1.4 ok\n%%EOF"
    assert calls == {"crossref": 2, "pdf": 2}


def test_a_permanent_error_is_not_retried(monkeypatch, tmp_path):
    calls = _network(monkeypatch, tmp_path, {"crossref": [Reply(404)], "pdf": [GOOD_PDF]})
    with pytest.raises(requests.exceptions.HTTPError):
        DoiResolver().resolve(SOURCE)
    assert calls["crossref"] == 1


def test_a_persistent_outage_still_surfaces_after_the_retries(monkeypatch, tmp_path):
    calls = _network(monkeypatch, tmp_path, {"crossref": [GOOD_LINKS], "pdf": [Reply(503)]})
    with pytest.raises(requests.exceptions.HTTPError):
        DoiResolver().resolve(SOURCE)
    assert calls["pdf"] == 3
