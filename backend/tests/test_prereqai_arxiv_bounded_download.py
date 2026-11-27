import pytest

from backend.ingestion.arxiv_resolver import ArxivResolver

pytestmark = pytest.mark.prereqai
URL = "https://arxiv.org/pdf/1706.03762"


class Streamed:
    def __init__(self, chunks, headers=None):
        self._chunks, self.headers, self.closed = chunks, headers or {}, False

    def iter_content(self, size):
        return iter(self._chunks)

    def raise_for_status(self):
        pass

    def close(self):
        self.closed = True


def _serve(monkeypatch, reply):
    monkeypatch.setattr("backend.ingestion.arxiv_resolver.requests.get", lambda url, **kw: reply if kw.get("stream") else pytest.fail("the body must be streamed"))


def test_a_body_within_the_limit_is_returned(monkeypatch):
    _serve(monkeypatch, Streamed([b"%PDF-", b"1.4"]))
    assert ArxivResolver()._download(URL) == b"%PDF-1.4"


def test_a_body_past_the_limit_is_refused_while_it_streams(monkeypatch):
    monkeypatch.setattr(ArxivResolver, "MAX_DOWNLOAD_BYTES", 1000)
    reply = Streamed([b"x" * 600] * 50)
    _serve(monkeypatch, reply)
    with pytest.raises(ValueError, match="larger than the limit"):
        ArxivResolver()._download(URL)
    assert reply.closed


def test_a_declared_size_past_the_limit_is_refused_before_reading(monkeypatch):
    monkeypatch.setattr(ArxivResolver, "MAX_DOWNLOAD_BYTES", 1000)
    reply = Streamed([b"x"], {"Content-Length": "999999"})
    _serve(monkeypatch, reply)
    with pytest.raises(ValueError, match="larger than the limit"):
        ArxivResolver()._download(URL)


def test_a_download_that_outlasts_the_deadline_is_stopped(monkeypatch):
    import time

    monkeypatch.setattr(ArxivResolver, "DOWNLOAD_SECONDS", 0.05)

    def slow():
        while True:
            time.sleep(0.03)
            yield b"x"

    _serve(monkeypatch, Streamed(slow()))
    with pytest.raises(TimeoutError):
        ArxivResolver()._download(URL)
