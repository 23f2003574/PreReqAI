"""Cooperative cancellation of the PreReqAI analysis workflow: checked before
the first stage and between stages, reported as status "cancelled" (distinct from
"failure"), never creating a session, never swallowing real errors."""
import json
import os
import signal

import fitz
import pytest

from backend.cli import EXIT_FAILURE, EXIT_OK, main
from backend.cli_common import EXIT_CANCELLED
from backend.pipeline.research_paper_pipeline import PipelineCancelled, ResearchPaperPipeline
from backend.platform import platform
from backend.session import session_manager


def _pdf(tmp_path):
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Paper\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11)
    path = tmp_path / "paper.pdf"
    path.write_bytes(document.tobytes())
    return str(path)


def _cancel_after(n):
    """should_cancel that turns True on its (n+1)th poll."""
    polls = {"count": 0}

    def should_cancel():
        polls["count"] += 1
        return polls["count"] > n

    return should_cancel


def test_normal_completion_is_unchanged_when_no_cancellation_is_requested(tmp_path):
    plain = platform.analyze(_pdf(tmp_path))
    never = platform.analyze(_pdf(tmp_path), should_cancel=lambda: False)

    assert plain["status"] == never["status"] == "success" and plain["report"] == never["report"]


def test_cancellation_before_processing_stops_before_any_stage(tmp_path):
    sessions_before = len(session_manager.sessions)

    outcome = platform.analyze(_pdf(tmp_path), diagnostics=True, should_cancel=lambda: True)

    assert outcome["status"] == "cancelled" and outcome["stage"] == "analysis" and "cancelled" in outcome["detail"]
    assert outcome["diagnostics"]["completed_stages"] == [] and outcome["diagnostics"]["stopped_after"] is None
    assert "session_id" not in outcome and "report" not in outcome
    assert len(session_manager.sessions) == sessions_before  # no session was opened


def test_cancellation_between_stages_stops_before_the_next_stage_and_reports_what_finished(tmp_path):
    outcome = platform.analyze(_pdf(tmp_path), diagnostics=True, should_cancel=_cancel_after(3))

    info = outcome["diagnostics"]
    assert outcome["status"] == "cancelled" and info["status"] == "cancelled"
    assert info["completed_stages"] == ["source_detector", "source_resolver", "ingestion"] == list(info["stage_seconds"])
    assert info["stopped_after"] == "ingestion" and "report" not in outcome


def test_cancelled_is_distinct_from_failure_but_uses_the_same_envelope_keys(tmp_path):
    cancelled = platform.analyze(_pdf(tmp_path), should_cancel=lambda: True)
    failed = platform.analyze(str(tmp_path / "missing.pdf"))

    assert cancelled["status"] == "cancelled" and failed["status"] == "failure"
    assert set(cancelled) == set(failed) == {"status", "stage", "detail", "error", "hint", "warnings"}


def test_real_errors_are_not_swallowed_by_cancellation_handling(tmp_path):
    with pytest.raises(PipelineCancelled):
        ResearchPaperPipeline().run(_pdf(tmp_path), should_cancel=lambda: True)

    outcome = platform.analyze(str(tmp_path / "missing.pdf"), should_cancel=lambda: False)
    assert outcome["status"] == "failure" and outcome["error"]["type"] == "FileNotFoundError"


def test_a_real_ctrl_c_during_a_stage_cancels_before_the_next_stage_and_exits_130(tmp_path, capsys, monkeypatch):
    parser = platform.analysis.section_parser
    real_parse = parser.parse
    monkeypatch.setattr(parser, "parse", lambda document: (os.kill(os.getpid(), signal.SIGINT), real_parse(document))[1])
    handler_before = signal.getsignal(signal.SIGINT)

    code = main(["prerequisites", "analyze", _pdf(tmp_path), "--json", "--diagnose"])

    outcome = json.loads(capsys.readouterr().out)
    assert code == EXIT_CANCELLED == 130 and outcome["status"] == "cancelled"
    assert outcome["diagnostics"]["stopped_after"] == "section_parser" and "session_id" not in outcome
    assert signal.getsignal(signal.SIGINT) is handler_before  # the CLI restores the previous handler


def test_the_cli_reports_cancellation_distinctly_from_failure_in_human_mode(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(platform, "analyze", lambda *a, **k: {"status": "cancelled", "stage": "analysis", "detail": "x", "error": None, "hint": None, "warnings": []})

    assert main(["prerequisites", "analyze", _pdf(tmp_path)]) == EXIT_CANCELLED
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("cancelled: analysis stopped") and "error:" not in captured.err

    monkeypatch.undo()
    assert main(["prerequisites", "analyze", str(tmp_path / "missing.pdf")]) == EXIT_FAILURE
    assert main(["prerequisites", "analyze", _pdf(tmp_path)]) == EXIT_OK
