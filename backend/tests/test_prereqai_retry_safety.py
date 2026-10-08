"""The workflow has no automatic retry: a retry is simply invoking it again.
That must be safe -- a failed attempt leaves nothing (no session, no cached
download, no stage state or warnings) that the next attempt would reuse, the
result is wholly the latest attempt's, and invalid input fails the same way
every time, before any work is done."""
from pathlib import Path

import pymupdf as fitz
import pytest
import requests

import backend.ingestion.arxiv_resolver as arxiv_resolver
from backend.pipeline.research_paper_pipeline import PIPELINE_STAGES
from backend.platform import AnalysisLimits, PreReqAIPlatform
from backend.session import session_manager

ARXIV = "https://arxiv.org/abs/1706.03762"


def _pdf_bytes():
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Paper\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11)
    return document.tobytes()


class _Response:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


@pytest.fixture
def platform(tmp_path, monkeypatch):
    platform = PreReqAIPlatform()
    monkeypatch.setattr(platform.analysis.source_resolver._resolvers["arxiv"], "CACHE_DIRECTORY", tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    return platform


def _replies(monkeypatch, *replies):
    queue = list(replies)

    def get(url, timeout=None):
        reply = queue.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return _Response(reply)
    monkeypatch.setattr(arxiv_resolver.requests, "get", get)
    return queue


def test_a_failed_attempt_then_a_successful_retry(platform, tmp_path, monkeypatch):
    _replies(monkeypatch, b"<html>Service unavailable</html>", _pdf_bytes())
    sessions = len(session_manager.sessions)

    first = platform.analyze(ARXIV, diagnostics=True)
    assert first["status"] == "failure" and "no PDF" in first["detail"]
    assert list((tmp_path / "cache").iterdir()) == [] and len(session_manager.sessions) == sessions  # nothing to reuse

    second = platform.analyze(ARXIV, diagnostics=True)
    assert second["status"] == "success" and second["diagnostics"]["completed_stages"] == list(PIPELINE_STAGES)
    assert [p.name for p in (tmp_path / "cache").iterdir()] == ["1706.03762.pdf"]


def test_an_interrupted_cache_write_leaves_nothing_for_the_retry(platform, tmp_path, monkeypatch):
    _replies(monkeypatch, _pdf_bytes(), _pdf_bytes())
    real_write = Path.write_bytes
    monkeypatch.setattr(Path, "write_bytes", lambda self, data: (real_write(self, data[:10]), (_ for _ in ()).throw(OSError("disk full")))[1])

    assert platform.analyze(ARXIV)["status"] == "failure"
    assert list((tmp_path / "cache").iterdir()) == []  # neither a truncated PDF nor a leftover .part file

    monkeypatch.setattr(Path, "write_bytes", real_write)
    assert platform.analyze(ARXIV)["status"] == "success"


def test_a_repeated_failure_is_reported_afresh_each_time(platform, tmp_path, monkeypatch):
    _replies(monkeypatch, requests.exceptions.ReadTimeout("slow"), requests.exceptions.ReadTimeout("slower"))

    first, second = platform.analyze(ARXIV, diagnostics=True), platform.analyze(ARXIV, diagnostics=True)

    assert first["status"] == second["status"] == "timeout"
    assert first["error"]["message"] == "slow" and second["error"]["message"] == "slower"  # each attempt's own error
    assert second["diagnostics"]["completed_stages"] == ["source_detector"] and list((tmp_path / "cache").iterdir()) == []


@pytest.mark.parametrize("paper, limits, stage", [
    ("see https://arxiv.org/abs/1706.03762 and 10.1000/xyz", None, "analysis"),
    (ARXIV, AnalysisLimits(max_seconds=-1), "configuration"),
])
def test_invalid_input_or_configuration_fails_identically_without_doing_work(platform, monkeypatch, paper, limits, stage):
    calls = _replies(monkeypatch, _pdf_bytes())

    attempts = [platform.analyze(paper, limits=limits, diagnostics=True) for _ in range(2)]

    assert attempts[0] == attempts[1] and attempts[0]["status"] == "failure" and attempts[0]["stage"] == stage
    assert attempts[0]["diagnostics"]["completed_stages"] == [] and len(calls) == 1  # never downloaded


def test_nothing_from_a_failed_attempt_leaks_into_the_successful_retry(platform, tmp_path, monkeypatch):
    _replies(monkeypatch, _pdf_bytes())
    with monkeypatch.context() as patch:
        patch.setattr(platform.analysis.learning_planner, "generate", lambda paper: (_ for _ in ()).throw(ValueError("planner broke")))
        failed = platform.analyze(ARXIV, diagnostics=True)
    assert failed["status"] == "failure" and failed["diagnostics"]["failed_stage"] == "learning_planner"

    retry = platform.analyze(ARXIV, diagnostics=True)

    info = retry["diagnostics"]
    assert retry["status"] == "success" and retry["warnings"] == [] and "error" not in retry and "detail" not in retry
    assert info["failed_stage"] is None and info["failed_after"] is None and info["completed_stages"] == list(PIPELINE_STAGES)
    assert retry["report"] == PreReqAIPlatform().analyze(str(tmp_path / "cache" / "1706.03762.pdf"))["report"]
