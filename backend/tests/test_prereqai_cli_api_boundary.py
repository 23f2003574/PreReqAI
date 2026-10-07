"""The CLI (`prerequisites analyze`) and the API (POST /api/prerequisites/analyze)
both go through PreReqAIPlatform.analyze(), so they share one result contract."""
import json

import fitz
from fastapi.testclient import TestClient

from backend.cli import EXIT_FAILURE, EXIT_OK, main
from backend.main import app

client = TestClient(app)


def _pdf_bytes() -> bytes:
    document = fitz.open()
    document.new_page().insert_text(
        (72, 72), "Attention Is All You Need\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11
    )
    return document.tobytes()


def test_cli_success_prints_a_human_summary_and_exits_zero(tmp_path, capsys):
    paper = tmp_path / "paper.pdf"
    paper.write_bytes(_pdf_bytes())

    code = main(["prerequisites", "analyze", str(paper)])

    out = capsys.readouterr().out
    assert code == EXIT_OK and out.startswith("Analysed '") and "(session " in out
    assert "concepts:" in out and "prerequisites:" in out and "{" not in out  # human text, not JSON


def test_cli_failure_prints_the_error_and_hint_to_stderr_and_exits_nonzero(tmp_path, capsys):
    code = main(["prerequisites", "analyze", str(tmp_path / "missing.pdf")])

    captured = capsys.readouterr()
    assert code == EXIT_FAILURE and captured.out == ""
    assert captured.err.startswith("error: analysis failed at stage 'analysis': Failed to process the uploaded paper")
    assert "Traceback" not in captured.err
    # a mistyped path is reported as a path problem, not as a bad paper
    assert "hint: Check the paper path: it must name an existing PDF file" in captured.err
    assert "Upload a text-based PDF" not in captured.err


def test_api_success_and_failure_use_the_same_envelope_as_the_cli_json(tmp_path, capsys):
    paper = tmp_path / "paper.pdf"
    paper.write_bytes(_pdf_bytes())
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")

    api_ok = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", paper.read_bytes(), "application/pdf")})
    assert main(["prerequisites", "analyze", str(paper), "--json"]) == EXIT_OK
    cli_ok = json.loads(capsys.readouterr().out)
    api_bad = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", bad.read_bytes(), "application/pdf")})
    assert main(["prerequisites", "analyze", str(bad), "--json"]) == EXIT_FAILURE
    cli_bad = json.loads(capsys.readouterr().out)

    assert api_ok.status_code == 200 and set(api_ok.json()) == set(cli_ok) and cli_ok["status"] == "success"
    assert cli_ok["stage"] == api_ok.json()["stage"] == "session_created" and cli_ok["warnings"] == []
    assert api_bad.status_code == 400 and set(api_bad.json()) == set(cli_bad) and cli_bad["status"] == "failure"
    assert cli_bad["stage"] == api_bad.json()["stage"] == "analysis" and cli_bad["hint"] == api_bad.json()["hint"]


def test_the_api_route_does_not_duplicate_the_workflow_conversion(tmp_path):
    from backend.api import prerequisite_routes
    from backend.platform import platform

    calls = []
    real = platform.analyze
    platform.analyze = lambda path: calls.append(path) or real(path)
    try:
        response = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", b"x", "application/pdf")})
    finally:
        platform.analyze = real

    assert len(calls) == 1 and response.json()["status"] == "failure"
    assert prerequisite_routes.platform is platform
