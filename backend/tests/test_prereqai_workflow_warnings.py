"""Warning semantics of the analysis workflow. No stage emits warnings today,
so a real run succeeds with an empty list; warnings put on a success reach the
API and CLI once each, in order, without changing the status; and a non-success
result never carries warnings (the workflow has no warning-with-failure state)."""
import json

import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient

from backend.api.workflow_result import (
    REQUIRED_REPORT_KEYS, cancelled_body, failure_body, limit_exceeded_body, success_body, terminal_violations, timeout_body,
)
from backend.cli import main
from backend.cli_common import EXIT_FAILURE, EXIT_OK
from backend.main import app
from backend.platform import PreReqAIPlatform, platform

client = TestClient(app)


def _pdf(tmp_path):
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Paper\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11)
    path = tmp_path / "paper.pdf"
    path.write_bytes(document.tobytes())
    return str(path)


def _success(warnings):
    report = {key: [] for key in REQUIRED_REPORT_KEYS} | {"paper": {"title": "A Paper"}, "statistics": {}}
    return success_body("Prerequisite Explorer", "session_created", warnings=warnings,
                        session_id="s-1", report=report, timings={"source_detector": 0.1})


def _through_api_and_cli(monkeypatch, capsys, tmp_path, outcome, *flags):
    monkeypatch.setattr(platform, "analyze", lambda *args, **kwargs: json.loads(json.dumps(outcome)))
    response = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", b"%PDF", "application/pdf")})
    code = main(["prerequisites", "analyze", _pdf(tmp_path), *flags])
    return response, code, capsys.readouterr()


def test_a_real_run_succeeds_without_warnings_everywhere(tmp_path, capsys):
    outcome = PreReqAIPlatform().analyze(_pdf(tmp_path), diagnostics=True)
    code = main(["prerequisites", "analyze", _pdf(tmp_path)])

    assert outcome["status"] == "success" and outcome["warnings"] == [] and outcome["diagnostics"]["warnings"] == []
    assert code == EXIT_OK and "warning:" not in capsys.readouterr().out


def test_one_warning_reaches_the_api_and_the_cli_once_and_keeps_the_success(monkeypatch, capsys, tmp_path):
    response, code, printed = _through_api_and_cli(monkeypatch, capsys, tmp_path, _success(["few concepts found"]))

    assert response.status_code == 200 and response.json()["status"] == "success"
    assert response.json()["warnings"] == ["few concepts found"]
    assert code == EXIT_OK and printed.out.count("warning: few concepts found") == 1


def test_multiple_warnings_keep_their_order_in_every_output(monkeypatch, capsys, tmp_path):
    warnings = ["second section empty", "no equations", "few concepts found"]
    response, code, printed = _through_api_and_cli(monkeypatch, capsys, tmp_path, _success(warnings))
    lines = [line.strip()[len("warning: "):] for line in printed.out.splitlines() if line.strip().startswith("warning:")]

    assert response.json()["warnings"] == warnings and lines == warnings and code == EXIT_OK
    assert terminal_violations(_success(warnings)) == []
    main(["prerequisites", "analyze", _pdf(tmp_path), "--json"])
    assert json.loads(capsys.readouterr().out)["warnings"] == warnings


@pytest.mark.parametrize("outcome", [
    failure_body("analysis", "broken", error=ValueError("broken")), cancelled_body("analysis", "stopped"),
    limit_exceeded_body("analysis", "too big"), timeout_body("analysis", "slow"),
])
def test_a_non_success_result_never_carries_warnings(outcome):
    assert outcome["warnings"] == [] and outcome["status"] != "success" and terminal_violations(outcome) == []


def test_a_failure_stays_a_failure_and_prints_no_warning_lines(monkeypatch, capsys, tmp_path):
    response, code, printed = _through_api_and_cli(monkeypatch, capsys, tmp_path, failure_body("analysis", "broken"))

    assert response.status_code == 400 and response.json()["warnings"] == []
    assert code == EXIT_FAILURE and "warning:" not in printed.out + printed.err
