"""One input -> result contract for the analysis workflow: the CLI and the API
return the same envelope for the same outcome, and every non-success outcome
is an HTTP error and a complete envelope (diagnostics included when asked)."""
import json

import fitz
from fastapi.testclient import TestClient

from backend.cli import main
from backend.cli_common import EXIT_FAILURE, EXIT_OK, EXIT_TIMEOUT
from backend.main import app
from backend.pipeline.research_paper_pipeline import PipelineResult
from backend.platform import platform

client = TestClient(app)
SEMANTIC_KEYS = ("status", "stage", "detail", "error", "hint", "warnings")


def _pdf(tmp_path):
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Paper\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11)
    path = tmp_path / "paper.pdf"
    path.write_bytes(document.tobytes())
    return path


def _both(paper, capsys, *flags):
    with open(paper, "rb") as handle:
        response = client.post("/api/prerequisites/analyze", files={"paper": ("paper.pdf", handle, "application/pdf")})
    code = main(["prerequisites", "analyze", str(paper), "--json", *flags])
    return response, code, json.loads(capsys.readouterr().out)


def test_success_is_the_same_result_through_the_api_and_the_cli(tmp_path, capsys):
    response, code, cli = _both(_pdf(tmp_path), capsys)

    api = response.json()
    assert response.status_code == 200 and code == EXIT_OK
    assert api["status"] == cli["status"] == "success" and api["stage"] == cli["stage"] == "session_created"
    assert api["feature"] == cli["feature"] and api["warnings"] == cli["warnings"] == []
    assert api["report"]["paper"] == cli["report"]["paper"] and set(api["timings"]) == set(cli["timings"])


def test_a_timeout_is_an_http_error_with_the_same_envelope_as_the_cli(tmp_path, capsys, monkeypatch):
    def slow(*args, **kwargs):
        raise TimeoutError("download took too long")
    monkeypatch.setattr(platform.analysis, "run", slow)

    response, code, cli = _both(_pdf(tmp_path), capsys)

    assert response.status_code == 504 and code == EXIT_TIMEOUT  # previously HTTP 200
    assert {key: response.json()[key] for key in SEMANTIC_KEYS} == {key: cli[key] for key in SEMANTIC_KEYS}
    assert cli["status"] == "timeout" and "session_id" not in cli and "report" not in cli


def test_an_incomplete_run_fails_at_finalization_with_diagnostics(tmp_path, capsys, monkeypatch):
    real_run = platform.analysis.run

    def partial(*args, **kwargs):
        result = real_run(*args, **kwargs)
        return PipelineResult(paper=result.paper, report={"paper": result.report["paper"]}, timings=result.timings)
    monkeypatch.setattr(platform.analysis, "run", partial)

    response, _, cli = _both(_pdf(tmp_path), capsys)
    code = main(["prerequisites", "analyze", str(_pdf(tmp_path)), "--diagnose"])  # used to raise KeyError

    assert response.status_code == 400 and response.json()["stage"] == cli["stage"] == "finalization"
    assert code == EXIT_FAILURE and "diagnostics:" in capsys.readouterr().err
