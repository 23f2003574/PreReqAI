"""Optional resource limits for a PreReqAI analysis run: a time budget checked
between stages and a maximum paper file size. Defaults are "no limit"; hitting a
limit ends the run with status "limit_exceeded" (not failure, not cancelled)."""
import json
import time

import pymupdf as fitz
import pytest

from backend.cli import EXIT_FAILURE, EXIT_OK, main
from backend.cli_common import EXIT_LIMIT_EXCEEDED
from backend.llm.config import InvalidConfigurationError
from backend.platform import AnalysisLimits, PreReqAIPlatform
from backend.session import session_manager


def _pdf(tmp_path):
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Paper\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11)
    path = tmp_path / "paper.pdf"
    path.write_bytes(document.tobytes())
    return str(path)


def _slow_section_parser(platform, seconds):
    parser = platform.analysis.section_parser
    real = parser.parse

    def slow(document):
        time.sleep(seconds)
        return real(document)

    parser.parse = slow
    return parser, real


def test_normal_execution_within_the_limits_is_unchanged(tmp_path):
    platform = PreReqAIPlatform()
    path = _pdf(tmp_path)

    plain = platform.analyze(path)
    limited = platform.analyze(path, limits=AnalysisLimits(max_seconds=60, max_file_bytes=10_000_000))

    assert plain["status"] == limited["status"] == "success" and plain["report"] == limited["report"]
    assert AnalysisLimits() == AnalysisLimits(None, None)  # the defaults are no limits


def test_the_time_limit_stops_the_run_between_stages_without_a_result_or_session(tmp_path):
    platform = PreReqAIPlatform()
    parser, real = _slow_section_parser(platform, 0.2)
    sessions = len(session_manager.sessions)
    try:
        outcome = platform.analyze(_pdf(tmp_path), diagnostics=True, limits=AnalysisLimits(max_seconds=0.1))
    finally:
        parser.parse = real

    assert outcome["status"] == "limit_exceeded" and outcome["stage"] == "analysis"
    assert outcome["error"]["type"] == "AnalysisLimitExceeded" and "time limit of 0.1 seconds" in outcome["detail"]
    assert outcome["diagnostics"]["stopped_after"] == "section_parser"  # stopped before the next stage started
    assert "session_id" not in outcome and "report" not in outcome and len(session_manager.sessions) == sessions
    assert set(outcome) - {"diagnostics"} == {"status", "stage", "detail", "error", "hint", "warnings"}


def test_the_file_size_limit_refuses_a_large_paper_before_any_processing(tmp_path):
    platform = PreReqAIPlatform()
    path = _pdf(tmp_path)

    outcome = platform.analyze(path, diagnostics=True, limits=AnalysisLimits(max_file_bytes=100))

    assert outcome["status"] == "limit_exceeded" and "larger than the limit of 100 bytes" in outcome["detail"]
    assert outcome["diagnostics"]["completed_stages"] == []  # nothing was processed


def test_a_limit_stop_is_distinct_from_cancellation_and_failure(tmp_path):
    platform = PreReqAIPlatform()
    path = _pdf(tmp_path)

    statuses = {
        platform.analyze(path, limits=AnalysisLimits(max_file_bytes=100))["status"],
        platform.analyze(path, should_cancel=lambda: True)["status"],
        platform.analyze(str(tmp_path / "missing.pdf"))["status"],
    }

    assert statuses == {"limit_exceeded", "cancelled", "failure"}


@pytest.mark.parametrize(
    "kwargs",
    [{"max_seconds": 0}, {"max_seconds": -1}, {"max_seconds": "5"}, {"max_seconds": True}, {"max_seconds": float("nan")},
     {"max_file_bytes": 0}, {"max_file_bytes": 1.5}, {"max_file_bytes": True}],
)
def test_invalid_limit_configuration_is_a_configuration_failure_before_any_work(tmp_path, kwargs):
    limits = AnalysisLimits(**kwargs)
    with pytest.raises(InvalidConfigurationError):
        limits.validate()

    outcome = PreReqAIPlatform().analyze(_pdf(tmp_path), diagnostics=True, limits=limits)

    assert outcome["status"] == "failure" and outcome["stage"] == "configuration"
    assert outcome["error"]["type"] == "InvalidConfigurationError" and outcome["diagnostics"]["completed_stages"] == []


def test_the_next_run_after_a_limit_stop_is_clean(tmp_path):
    platform = PreReqAIPlatform()
    path = _pdf(tmp_path)
    fresh = PreReqAIPlatform().analyze(path)

    assert platform.analyze(path, limits=AnalysisLimits(max_file_bytes=100))["status"] == "limit_exceeded"
    parser, real = _slow_section_parser(platform, 0.2)
    try:
        assert platform.analyze(path, limits=AnalysisLimits(max_seconds=0.1))["status"] == "limit_exceeded"
    finally:
        parser.parse = real

    again = platform.analyze(path)
    assert again["status"] == "success" and again["report"] == fresh["report"]


def test_the_cli_reports_a_limit_with_its_own_exit_code_and_applies_the_flags(tmp_path, capsys):
    path = _pdf(tmp_path)

    assert main(["prerequisites", "analyze", path, "--max-file-mb", "0.00001"]) == EXIT_LIMIT_EXCEEDED
    err = capsys.readouterr().err
    assert err.startswith("error: limit exceeded: The paper is larger than the limit") and "hint:" in err

    assert main(["prerequisites", "analyze", path, "--max-seconds", "0", "--json"]) == EXIT_FAILURE  # invalid limit value
    assert json.loads(capsys.readouterr().out)["stage"] == "configuration"

    assert main(["prerequisites", "analyze", path, "--max-seconds", "60", "--max-file-mb", "50"]) == EXIT_OK
    capsys.readouterr()
