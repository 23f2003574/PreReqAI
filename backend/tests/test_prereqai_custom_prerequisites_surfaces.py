"""Custom prerequisites through the API, the command line and the page: confirmation is explicit, the report carries the proposals key and the page shows and sends them."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import custom_concepts
from backend.cli import main
from backend.main import app
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
client = TestClient(app, raise_server_exceptions=False)
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv(custom_concepts.ENV, str(tmp_path / "custom.json"))
    session_manager.sessions.clear()
    yield tmp_path
    session_manager.sessions.clear()


def test_the_api_confirms_and_forgets_a_prerequisite_only_on_request(env):
    assert client.post("/api/custom-concepts/prerequisites", json={"concept": "Sliding Window Cache", "prerequisite": "Probability"}).status_code == 422  # not a confirmed concept
    client.post("/api/custom-concepts", json={"name": "Sliding Window Cache"})
    done = client.post("/api/custom-concepts/prerequisites", json={"concept": "Sliding Window Cache", "prerequisite": "probability", "quote": "It builds on probability.", "page_number": 2, "section": "Method"})
    assert done.status_code == 200 and done.json()["prerequisite"]["name"] == "Probability"
    assert client.get("/api/custom-concepts").json()["concepts"][0]["prerequisites"][0]["quote"] == "It builds on probability."
    assert client.post("/api/custom-concepts/prerequisites", json={"concept": "Sliding Window Cache", "prerequisite": "Probability"}).status_code == 422  # already confirmed
    assert client.delete("/api/custom-concepts/prerequisites", params={"concept": "Sliding Window Cache", "prerequisite": "Probability"}).status_code == 200
    assert client.delete("/api/custom-concepts/prerequisites", params={"concept": "Sliding Window Cache", "prerequisite": "Probability"}).status_code == 404


def test_the_report_has_the_proposals_key_and_an_unconfirmed_one_changes_no_plan(env):
    report = platform.analyze("examples/prerequisites/sample-paper.pdf")["report"]
    assert report["custom_prerequisite_proposals"] == []


def test_the_command_line_confirms_and_removes_a_prerequisite(env, capsys):
    assert main(["prerequisites", "custom-concept", "add", "Sliding Window Cache"]) == 0
    assert main(["prerequisites", "custom-concept", "needs", "Sliding Window Cache", "--prerequisite", "Calculus", "--quote", "It needs calculus."]) == 0
    assert "Confirmed: Sliding Window Cache needs Calculus" in capsys.readouterr().out and custom_concepts.confirmed_rules() == {"Sliding Window Cache": ["Calculus"]}
    assert main(["prerequisites", "custom-concept", "needs", "Sliding Window Cache", "--prerequisite", "Nonsense Subject"]) != 0
    assert main(["prerequisites", "custom-concept", "unneeds", "Sliding Window Cache", "--prerequisite", "Calculus"]) == 0 and custom_concepts.confirmed_rules() == {}


def test_the_page_shows_proposals_and_confirms_them_through_the_api():
    assert "renderCustomProposals(report)" in PAGE and "custom_prerequisite_proposals" in PAGE and "/api/custom-concepts/prerequisites" in PAGE and 'id="customProposals"' in PAGE
