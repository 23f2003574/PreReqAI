"""The workflow's public output is one canonical, plain-JSON shape: the API and
the CLI return the very same value, empty and optional fields look the same in
every result, collections come out in a stable order, and a value that is not
plain JSON fails the run loudly instead of being converted differently by each
adapter."""
import json
import subprocess
import sys

import fitz
import pytest
from fastapi.testclient import TestClient

from backend.api.workflow_result import json_violations
from backend.cli import main
from backend.main import app
from backend.platform import platform

client = TestClient(app)
NON_SUCCESS_KEYS = ["detail", "error", "hint", "stage", "status", "warnings"]


def _pdf(tmp_path, body="We use softmax and attention and gradient descent."):
    document = fitz.open()
    document.new_page().insert_text((72, 72), f"A Paper\n\nAbstract\n{body}\n\n1 Introduction\n{body}\n", fontsize=11)
    path = tmp_path / "paper.pdf"
    path.write_bytes(document.tobytes())
    return path


def _both(paper, capsys):
    with open(paper, "rb") as handle:
        api = client.post("/api/prerequisites/analyze", files={"paper": ("paper.pdf", handle, "application/pdf")}).json()
    main(["prerequisites", "analyze", str(paper), "--json"])
    return api, json.loads(capsys.readouterr().out)


def _without_run_ids(outcome):
    return {key: value for key, value in outcome.items() if key not in ("session_id", "timings")}


def test_a_success_is_the_same_plain_json_value_through_the_api_and_the_cli(tmp_path, capsys):
    api, cli = _both(_pdf(tmp_path), capsys)

    assert api["status"] == "success" and json_violations(api) == []
    assert _without_run_ids(api) == _without_run_ids(cli) and list(api["timings"]) == list(cli["timings"])


def test_report_collections_come_out_in_the_same_order_in_every_process(tmp_path):
    paper = _pdf(tmp_path, "We use softmax, attention, convolution, gradient descent, backpropagation and linear algebra.")
    script = f"import json; from backend.platform import PreReqAIPlatform; print(json.dumps(PreReqAIPlatform().analyze({str(paper)!r})['report']))"
    outputs = {subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True,
                              env={"PYTHONHASHSEED": seed, "PATH": ""}).stdout for seed in ("1", "2")}

    assert len(outputs) == 1  # no collection's order depends on set/hash order


def test_an_empty_paper_has_empty_lists_not_missing_or_null_fields(tmp_path, capsys):
    api, cli = _both(_pdf(tmp_path, "Nothing technical is discussed here."), capsys)

    assert api["status"] == "success" and api["warnings"] == [] and _without_run_ids(api) == _without_run_ids(cli)
    for key in ("concepts", "prerequisites", "missing_prerequisites"):
        assert isinstance(api["report"][key], list)


def test_a_failure_has_the_same_keys_and_values_through_the_api_and_the_cli(tmp_path, capsys):
    paper = tmp_path / "broken.pdf"
    paper.write_bytes(b"not a pdf")

    api, cli = _both(paper, capsys)

    assert sorted(api) == sorted(cli) == NON_SUCCESS_KEYS
    assert api["status"] == "failure" and api["error"]["type"] == cli["error"]["type"] and api["hint"] == cli["hint"]


def test_a_value_that_is_not_plain_json_fails_the_run_instead_of_being_stringified(tmp_path, capsys, monkeypatch):
    real = platform.analysis.report_generator.generate
    monkeypatch.setattr(platform.analysis.report_generator, "generate", lambda paper: {**real(paper), "concepts": {"softmax"}})

    api, cli = _both(_pdf(tmp_path), capsys)

    assert api["status"] == cli["status"] == "failure" and api["stage"] == cli["stage"] == "finalization"
    assert "result.report.concepts is a set, not plain JSON" in cli["detail"]
