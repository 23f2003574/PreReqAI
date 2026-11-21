"""Custom concepts through the API, the command line and the page: candidates in the report, explicit confirmation, detection afterwards, and clear errors."""
import json
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
MIXTRAL = "backend/prereqai_eval/benchmark/pdfs/mixtral.pdf"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv(custom_concepts.ENV, str(tmp_path / "custom.json"))
    session_manager.sessions.clear()
    yield tmp_path
    session_manager.sessions.clear()


def test_the_report_lists_candidates_and_the_api_confirms_one_only_on_request(env):
    outcome = platform.analyze(MIXTRAL)
    report = outcome["report"]
    candidates = report["candidate_concepts"]
    assert isinstance(candidates, list) and all({"term", "sentence", "page_number", "section", "reason", "mentions"} <= set(c) for c in candidates)
    assert client.get("/api/custom-concepts").json()["concepts"] == []  # listing candidates added nothing
    added = client.post("/api/custom-concepts", json={"name": "Sliding Window Cache", "aliases": [], "definition": "x"})
    assert added.status_code == 200 and added.json()["concept"]["name"] == "Sliding Window Cache"
    assert [c["name"] for c in client.get("/api/custom-concepts").json()["concepts"]] == ["Sliding Window Cache"]
    assert client.post("/api/custom-concepts", json={"name": "Softmax"}).status_code == 422 and client.delete("/api/custom-concepts", params={"name": "Nope Nope"}).status_code == 404
    assert client.delete("/api/custom-concepts", params={"name": "sliding window cache"}).status_code == 200


def test_the_command_line_lists_confirms_and_forgets_and_shows_candidates(env, capsys):
    session_id = platform.analyze(MIXTRAL)["session_id"]
    assert main(["prerequisites", "candidates", session_id, "--json"]) == 0
    assert "candidate_concepts" in json.loads(capsys.readouterr().out)
    assert main(["prerequisites", "custom-concept", "add", "Expert Routing", "--alias", "router balance"]) == 0 and "Confirmed Expert Routing" in capsys.readouterr().out
    assert main(["prerequisites", "custom-concept", "list"]) == 0 and "Expert Routing (also: router balance)" in capsys.readouterr().out
    assert main(["prerequisites", "custom-concept", "add", "Softmax"]) != 0 and "already a concept" in capsys.readouterr().err
    assert main(["prerequisites", "custom-concept", "remove", "Expert Routing"]) == 0 and main(["prerequisites", "custom-concept", "remove", "Expert Routing"]) != 0


def test_a_confirmed_concept_is_detected_in_the_next_analysis_and_the_page_offers_confirmation(env):
    assert "Mixtral" not in platform.analyze(MIXTRAL)["report"]["concepts"]  # the model's own name appears throughout the paper and is not in the registry
    custom_concepts.add("Mixtral")
    report = platform.analyze(MIXTRAL)["report"]
    assert "Mixtral" in report["concepts"] and "Mixtral" in report["concepts_without_prerequisite_rules"]  # detected, and reported as having no rules rather than as needing nothing
    assert "mixtral" not in {c["term"].lower() for c in report["candidate_concepts"]}
    assert 'id="candidatebox"' in PAGE and "/api/custom-concepts" in PAGE and "Suggestions only" in PAGE
