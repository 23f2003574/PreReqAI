"""Cancellation and timeout are their own terminal results at the workflow
boundary: never a success or a generic failure, with the stages finished before
them kept, the same state through the API and the CLI, and no effect on the
next run."""
import json

import pymupdf as fitz
import pytest
import requests
import urllib3
from fastapi.testclient import TestClient

from backend.api.workflow_result import terminal_violations
from backend.cli import main
from backend.cli_common import EXIT_TIMEOUT
from backend.main import app
from backend.pipeline.research_paper_pipeline import PIPELINE_STAGES
from backend.platform import PreReqAIPlatform, platform as shared_platform
from backend.session import session_manager

client = TestClient(app)


def _pdf(tmp_path):
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Paper\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11)
    path = tmp_path / "paper.pdf"
    path.write_bytes(document.tobytes())
    return str(path)


def _raise(exc):
    def stage(*args, **kwargs):
        raise exc
    return stage


@pytest.fixture
def platform():
    return PreReqAIPlatform()


def test_cancellation_is_its_own_terminal_result(platform, tmp_path):
    sessions = len(session_manager.sessions)

    outcome = platform.analyze(_pdf(tmp_path), should_cancel=lambda: True, diagnostics=True)

    assert outcome["status"] == "cancelled" and outcome["error"] is None and terminal_violations(outcome) == []
    assert outcome["diagnostics"]["completed_stages"] == [] and len(session_manager.sessions) == sessions


@pytest.mark.parametrize("exc", [
    requests.exceptions.ReadTimeout("read timed out"),
    TimeoutError("timed out"),
    requests.exceptions.ConnectionError(urllib3.exceptions.ReadTimeoutError(None, "/pdf", "read timed out")),  # body read timeout
])
def test_a_timeout_is_its_own_terminal_result_however_it_is_raised(platform, tmp_path, monkeypatch, exc):
    monkeypatch.setattr(platform.analysis.ingestion, "ingest", _raise(exc))

    outcome = platform.analyze(_pdf(tmp_path), diagnostics=True)

    assert outcome["status"] == "timeout" and terminal_violations(outcome) == []
    assert outcome["diagnostics"]["completed_stages"] == ["source_detector", "source_resolver"]
    assert outcome["diagnostics"]["stopped_after"] == "source_resolver" and outcome["diagnostics"]["failed_after"] is None


def test_a_timeout_wrapped_by_a_stage_is_still_a_timeout_but_other_errors_are_failures(platform, tmp_path, monkeypatch):
    def wrapping(paper):
        try:
            raise TimeoutError("lookup timed out")
        except TimeoutError as cause:
            raise RuntimeError("concept lookup failed") from cause
    monkeypatch.setattr(platform.analysis.concept_detector, "detect", wrapping)
    assert platform.analyze(_pdf(tmp_path))["status"] == "timeout"

    monkeypatch.setattr(platform.analysis.concept_detector, "detect", _raise(requests.exceptions.ConnectionError("refused")))
    assert platform.analyze(_pdf(tmp_path))["status"] == "failure"


def test_cancellation_after_an_intermediate_stage_keeps_the_stages_before_it(platform, tmp_path):
    finished = []
    stop_after = PIPELINE_STAGES.index("concept_detector") + 1

    outcome = platform.analyze(_pdf(tmp_path), diagnostics=True, should_cancel=lambda: finished.append(1) or len(finished) > stop_after)

    info = outcome["diagnostics"]
    assert outcome["status"] == "cancelled" and info["stopped_after"] == "concept_detector"
    assert info["completed_stages"] == list(PIPELINE_STAGES[:stop_after]) and "report" not in outcome


def test_api_and_cli_see_the_same_timeout_and_cli_shows_where_it_stopped(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(shared_platform.analysis.ingestion, "ingest", _raise(TimeoutError("slow")))
    response = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", open(_pdf(tmp_path), "rb"), "application/pdf")})
    code = main(["prerequisites", "analyze", _pdf(tmp_path), "--json"])
    cli = json.loads(capsys.readouterr().out)

    assert response.status_code == 504 and code == EXIT_TIMEOUT
    assert {k: response.json()[k] for k in ("status", "stage", "error")} == {k: cli[k] for k in ("status", "stage", "error")}
    assert main(["prerequisites", "analyze", _pdf(tmp_path), "--diagnose"]) == EXIT_TIMEOUT
    printed = capsys.readouterr()
    assert "2 stages completed; stopped after source_resolver" in printed.err and printed.out == ""


def test_a_clean_run_after_a_cancellation_and_a_timeout_succeeds_normally(platform, tmp_path, monkeypatch):
    paper = _pdf(tmp_path)
    expected = PreReqAIPlatform().analyze(paper)["report"]
    platform.analyze(paper, should_cancel=lambda: True)
    with monkeypatch.context() as patch:
        patch.setattr(platform.analysis.ingestion, "ingest", _raise(TimeoutError("slow")))
        assert platform.analyze(paper)["status"] == "timeout"

    outcome = platform.analyze(paper, diagnostics=True)

    assert outcome["status"] == "success" and outcome["report"] == expected
    assert outcome["diagnostics"]["completed_stages"] == list(PIPELINE_STAGES) and outcome["diagnostics"]["stopped_after"] is None
