"""The primary PreReqAI workflow (paper analysis) has no configuration of its
own: no settings object, environment variables or config file. Its one varying
input is the paper path/upload. These tests pin that: it runs with an empty
environment and no arguments to the platform, and every invalid value of that
input is reported in the structured failure result, never raised."""
import os
import subprocess
import sys
from pathlib import Path

import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient

from backend.cli import EXIT_FAILURE, main
from backend.main import app
from backend.platform import PreReqAIPlatform, platform

ROOT = Path(__file__).resolve().parents[2]


def test_the_platform_needs_no_configuration_and_runs_in_an_empty_environment(tmp_path):
    paper = tmp_path / "paper.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Paper\n\nAbstract\nWe use softmax.\n", fontsize=11)
    paper.write_bytes(document.tobytes())
    program = (
        "import json; from backend.platform import PreReqAIPlatform; "
        f"r = PreReqAIPlatform().analyze({str(paper)!r}); print(json.dumps([r['status'], r['stage'], r['warnings']]))"
    )

    run = subprocess.run([sys.executable, "-c", program], cwd=ROOT, capture_output=True, text=True,
                         env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT)})  # no other variables

    assert run.returncode == 0, run.stderr
    assert run.stdout.strip().splitlines()[-1] == '["success", "session_created", []]'
    assert PreReqAIPlatform() is not None  # constructed with no arguments, as before


def _invalid_inputs(tmp_path):
    empty_pdf = tmp_path / "empty.pdf"
    empty_pdf.write_bytes(b"")
    text = tmp_path / "notes.txt"
    text.write_text("hello")
    return {"a directory": str(tmp_path), "an empty file": str(empty_pdf), "an empty path": "", "a non-PDF file": str(text),
            "a missing file": str(tmp_path / "missing.pdf")}


@pytest.mark.parametrize("case", ["a directory", "an empty file", "an empty path", "a non-PDF file", "a missing file"])
def test_every_invalid_input_value_is_a_structured_failure_with_the_same_shape(tmp_path, case, capsys):
    path = _invalid_inputs(tmp_path)[case]

    outcome = platform.analyze(path)

    assert outcome["status"] == "failure" and outcome["stage"] == "analysis" and outcome["warnings"] == []
    assert outcome["detail"].startswith("Failed to process the uploaded paper") and outcome["error"]["type"] and outcome["hint"]
    assert main(["prerequisites", "analyze", path]) == EXIT_FAILURE  # the CLI reports the same failure, exit 1
    assert "Traceback" not in capsys.readouterr().err


def test_the_api_reports_an_empty_upload_in_the_same_failure_envelope():
    response = TestClient(app).post("/api/prerequisites/analyze", files={"paper": ("empty.pdf", b"", "application/pdf")})

    body = response.json()
    assert response.status_code == 400 and body["status"] == "failure" and body["stage"] == "analysis"
    assert set(body) == {"status", "stage", "detail", "error", "hint", "warnings"}
