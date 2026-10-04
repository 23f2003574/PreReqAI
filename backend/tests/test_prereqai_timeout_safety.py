"""An operation that times out (in practice the arXiv download, which already
has its own timeout) ends the PreReqAI run with status "timeout": distinct from
failure, cancellation and a configured limit, with no session or partial file."""
import json

import fitz
import pytest
import requests

import backend.ingestion.arxiv_resolver as arxiv_resolver
from backend.cli import EXIT_FAILURE, EXIT_OK, main
from backend.cli_common import EXIT_CANCELLED, EXIT_LIMIT_EXCEEDED, EXIT_TIMEOUT
from backend.platform import AnalysisLimits, PreReqAIPlatform
from backend.session import session_manager

ARXIV = "https://arxiv.org/abs/9999.12345"


def _pdf_bytes():
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Paper\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11)
    return document.tobytes()


class _Response:
    content = b""

    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


@pytest.fixture
def platform_with_cache(tmp_path, monkeypatch):
    platform = PreReqAIPlatform()
    resolver = platform.analysis.source_resolver._resolvers["arxiv"]
    monkeypatch.setattr(resolver, "CACHE_DIRECTORY", tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    return platform, tmp_path / "cache"


def _download(monkeypatch, behaviour):
    monkeypatch.setattr(arxiv_resolver.requests, "get", behaviour)


def _times_out(*args, **kwargs):
    raise requests.exceptions.ReadTimeout("read timed out after 60s")


def test_a_download_that_completes_within_its_timeout_is_a_normal_success(platform_with_cache, monkeypatch):
    platform, cache = platform_with_cache
    calls = []
    _download(monkeypatch, lambda url, timeout=None: calls.append(timeout) or _Response(_pdf_bytes()))

    outcome = platform.analyze(ARXIV)

    assert outcome["status"] == "success" and calls == [60]  # the existing 60 s download timeout is what applies
    assert (cache / "9999.12345.pdf").exists()


def test_a_timed_out_download_is_a_timeout_result_with_no_session_or_partial_file(platform_with_cache, monkeypatch):
    platform, cache = platform_with_cache
    _download(monkeypatch, _times_out)
    sessions = len(session_manager.sessions)

    outcome = platform.analyze(ARXIV, diagnostics=True)

    assert outcome["status"] == "timeout" and outcome["stage"] == "analysis" and "timed out" in outcome["detail"]
    assert outcome["error"] == {"type": "ReadTimeout", "message": "read timed out after 60s"} and outcome["hint"]
    assert set(outcome) - {"diagnostics"} == {"status", "stage", "detail", "error", "hint", "warnings"}
    assert outcome["diagnostics"]["completed_stages"] == ["source_detector"] and outcome["diagnostics"]["stopped_after"] == "source_detector"
    assert "session_id" not in outcome and "report" not in outcome and len(session_manager.sessions) == sessions
    assert list(cache.iterdir()) == []  # nothing half-downloaded was left behind


def test_timeout_is_distinct_from_failure_cancellation_and_a_configured_limit(platform_with_cache, tmp_path, monkeypatch):
    platform, _ = platform_with_cache
    paper = tmp_path / "paper.pdf"
    paper.write_bytes(_pdf_bytes())
    _download(monkeypatch, _times_out)

    statuses = {
        "timeout": platform.analyze(ARXIV)["status"],
        "failure": platform.analyze(str(tmp_path / "missing.pdf"))["status"],
        "cancelled": platform.analyze(str(paper), should_cancel=lambda: True)["status"],
        "limit_exceeded": platform.analyze(str(paper), limits=AnalysisLimits(max_file_bytes=10))["status"],
    }

    assert statuses == {name: name for name in ("timeout", "failure", "cancelled", "limit_exceeded")}
    assert len({EXIT_OK, EXIT_FAILURE, EXIT_TIMEOUT, EXIT_LIMIT_EXCEEDED, EXIT_CANCELLED}) == 5


def test_an_ordinary_download_error_is_still_a_plain_failure(platform_with_cache, monkeypatch):
    platform, _ = platform_with_cache

    def refused(*args, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    _download(monkeypatch, refused)

    outcome = platform.analyze(ARXIV)

    assert outcome["status"] == "failure" and outcome["error"]["type"] == "ConnectionError"


def test_the_next_run_after_a_timeout_is_clean(platform_with_cache, tmp_path, monkeypatch):
    platform, cache = platform_with_cache
    _download(monkeypatch, _times_out)
    assert platform.analyze(ARXIV)["status"] == "timeout"

    _download(monkeypatch, lambda url, timeout=None: _Response(_pdf_bytes()))
    recovered = platform.analyze(ARXIV)
    paper = tmp_path / "paper.pdf"
    paper.write_bytes(_pdf_bytes())

    assert recovered["status"] == "success" and recovered["report"] == platform.analyze(str(paper))["report"]


def test_the_cli_reports_a_timeout_with_its_own_exit_code(platform_with_cache, monkeypatch, capsys):
    from backend.platform import platform as shared

    _, cache = platform_with_cache
    resolver = shared.analysis.source_resolver._resolvers["arxiv"]
    monkeypatch.setattr(resolver, "CACHE_DIRECTORY", cache)
    _download(monkeypatch, _times_out)

    assert main(["prerequisites", "analyze", ARXIV]) == EXIT_TIMEOUT == 124
    err = capsys.readouterr().err
    assert err.startswith("error: timed out at stage 'analysis': The analysis timed out") and "hint:" in err

    assert main(["prerequisites", "analyze", ARXIV, "--json"]) == EXIT_TIMEOUT
    assert json.loads(capsys.readouterr().out)["status"] == "timeout"
