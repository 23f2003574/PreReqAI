"""The same invalid source is classified the same way by the CLI and the HTTP API: a failure at the analysis stage with an
actionable hint. Each keeps its own convention for the code (CLI exit 1, HTTP 422)."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.cli import main
from backend.cli_common import EXIT_FAILURE
from backend.main import app

client = TestClient(app)


@pytest.mark.parametrize("source", ["https://example.com/paper.pdf", "not-a-source"])
def test_an_invalid_source_fails_at_the_analysis_stage_on_both_interfaces(source, capsys):
    response = client.post("/api/prerequisites/analyze", data={"source": source})
    http = response.json()
    assert response.status_code == 422 and http["status"] == "failure" and http["stage"] == "analysis" and http["hint"]

    assert main(["prerequisites", "analyze", source, "--json"]) == EXIT_FAILURE
    cli = json.loads(capsys.readouterr().out)
    assert cli["status"] == "failure" and cli["stage"] == http["stage"] and cli["hint"]
    assert "report" not in cli and "report" not in http and "session_id" not in cli


def test_a_valid_source_still_succeeds_on_both(capsys):
    path = "examples/prerequisites/sample-paper.pdf"
    assert main(["prerequisites", "analyze", path, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "success"
    with open(path, "rb") as handle:
        assert client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["status"] == "success"
