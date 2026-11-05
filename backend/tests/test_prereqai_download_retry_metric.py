"""diagnostics.download_retries counts the transient download failures a run retried (a measured count, no inputs or URLs)."""
import pymupdf as fitz
import pytest
import requests

import backend.ingestion.arxiv_resolver as arxiv_resolver
from backend.platform import PreReqAIPlatform

pytestmark = pytest.mark.prereqai


def _pdf():
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Attention and softmax in a transformer.")
    return document.tobytes()


class _Response:
    status_code = 200

    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


def _platform(tmp_path, monkeypatch, *replies):
    platform = PreReqAIPlatform()
    resolver = platform.analysis.source_resolver._resolvers["arxiv"]
    monkeypatch.setattr(resolver, "CACHE_DIRECTORY", tmp_path / "cache")
    monkeypatch.setattr(resolver, "RETRY_DELAYS", (0.0, 0.0))
    (tmp_path / "cache").mkdir()
    queue = list(replies)

    def get(url, timeout=None):
        reply = queue.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return _Response(reply)

    monkeypatch.setattr(arxiv_resolver.requests, "get", get)
    return platform


def test_each_retried_download_failure_is_counted(tmp_path, monkeypatch):
    flaky = requests.exceptions.ConnectionError("dropped")
    platform = _platform(tmp_path, monkeypatch, flaky, flaky, _pdf())
    outcome = platform.analyze("arXiv:1706.03762", diagnostics=True)
    assert outcome["status"] == "success"
    assert outcome["diagnostics"]["download_retries"] == 2


def test_a_clean_download_and_a_local_file_count_zero(tmp_path, monkeypatch):
    platform = _platform(tmp_path, monkeypatch, _pdf())
    assert platform.analyze("arXiv:1706.03762", diagnostics=True)["diagnostics"]["download_retries"] == 0
    local = tmp_path / "p.pdf"
    local.write_bytes(_pdf())
    assert platform.analyze(str(local), diagnostics=True)["diagnostics"]["download_retries"] == 0


def test_the_count_is_reported_for_a_failed_run_and_does_not_leak_into_the_next(tmp_path, monkeypatch):
    flaky = requests.exceptions.ConnectionError("dropped")
    platform = _platform(tmp_path, monkeypatch, flaky, flaky, flaky, _pdf())
    failed = platform.analyze("arXiv:1706.03762", diagnostics=True)  # two retries, then the third failure surfaces
    assert failed["status"] == "failure" and failed["diagnostics"]["download_retries"] == 2
    assert arxiv_resolver.RETRY_COUNTER.get() is None  # the run's counter is gone once it ends
    assert platform.analyze("arXiv:1706.03762", diagnostics=True)["diagnostics"]["download_retries"] == 0
