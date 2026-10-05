"""PreReqAI release-readiness check: one fast pass over the release checklist
through public behavior only (the platform entrypoint, the HTTP API and the
CLI). The full release check is this file together with every focused PreReqAI
test, including the end-to-end CLI smoke test:

    python3 -m pytest -q backend/tests/test_prereqai_*.py backend/tests/test_prerequisite_endpoint.py
"""
import json

import fitz
import pytest
from fastapi.testclient import TestClient

from backend.api.workflow_result import TERMINAL_STATUSES, terminal_violations
from backend.cli import main
from backend.cli_common import EXIT_CANCELLED, EXIT_FAILURE, EXIT_LIMIT_EXCEEDED, EXIT_OK, EXIT_TIMEOUT
from backend.main import app
from backend.platform import AnalysisLimits, platform

client = TestClient(app)


@pytest.fixture(scope="module")
def paper(tmp_path_factory):
    document = fitz.open()
    document.new_page().insert_text(
        (72, 72), "Attention Is All You Need\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11
    )
    path = tmp_path_factory.mktemp("release") / "paper.pdf"
    path.write_bytes(document.tobytes())
    return str(path)


def _cli_json(capsys, *args):
    code = main(["prerequisites", "analyze", *args, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_the_workflow_is_reachable_and_valid_input_succeeds_everywhere(paper, capsys):
    with open(paper, "rb") as handle:
        response = client.post("/api/prerequisites/analyze", files={"paper": ("paper.pdf", handle, "application/pdf")})
    code, cli = _cli_json(capsys, paper)

    for outcome in (response.json(), cli, platform.analyze(paper)):
        assert outcome["status"] == "success" and outcome["warnings"] == [] and terminal_violations(outcome) == []
    assert response.status_code == 200 and code == EXIT_OK


def test_invalid_input_fails_cleanly_with_a_classified_error(capsys):
    code, cli = _cli_json(capsys, "not a paper")

    assert code == EXIT_FAILURE and cli["status"] == "failure" and terminal_violations(cli) == []
    assert cli["error"]["type"] == "ValueError" and cli["hint"] and cli["warnings"] == [] and "report" not in cli


def test_every_terminal_state_is_distinct_with_its_own_exit_code(paper, capsys, monkeypatch):
    def timing_out(path):
        raise TimeoutError("slow")

    with monkeypatch.context() as patch:
        patch.setattr(platform.analysis.ingestion, "ingest", timing_out)
        timeout = _cli_json(capsys, paper)
    with monkeypatch.context() as patch:
        patch.setattr("threading.Event.is_set", lambda self: True)
        cancelled = _cli_json(capsys, paper)
    limited = _cli_json(capsys, paper, "--max-file-mb", "0.0001")
    failed = _cli_json(capsys, "not a paper")

    results = {"timeout": timeout, "cancelled": cancelled, "limit_exceeded": limited, "failure": failed}
    assert {status: (code, outcome["status"]) for status, (code, outcome) in results.items()} == {
        "timeout": (EXIT_TIMEOUT, "timeout"), "cancelled": (EXIT_CANCELLED, "cancelled"),
        "limit_exceeded": (EXIT_LIMIT_EXCEEDED, "limit_exceeded"), "failure": (EXIT_FAILURE, "failure"),
    }
    assert all(outcome["status"] in TERMINAL_STATUSES and terminal_violations(outcome) == [] for _, outcome in results.values())


def test_repeated_runs_do_not_leak_state(paper):
    first = platform.analyze(paper)
    platform.analyze("not a paper")
    platform.analyze(paper, limits=AnalysisLimits(max_seconds=0.000001))
    second = platform.analyze(paper)

    assert second["status"] == "success" and second["warnings"] == [] and second["report"] == first["report"]
    assert second["session_id"] != first["session_id"]
