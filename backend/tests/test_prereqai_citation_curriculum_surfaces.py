"""Citation-aware curriculum through the API, the command line and the page."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.cli import main
from backend.main import app
from backend.models import PaperReference
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
client = TestClient(app, raise_server_exceptions=False)
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
CITED, CITING = "Sparse Mixtures of Expert Language Models", "Fast Inference for Sparse Language Models"


@pytest.fixture
def pair(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    ids = []
    for path, title in (("examples/prerequisites/sample-paper.pdf", CITING), ("backend/prereqai_eval/benchmark/pdfs/mixtral.pdf", CITED)):
        sid = platform.analyze(path)["session_id"]
        session = session_manager.get(sid)
        session.paper_title, session.report["paper"] = title, {**session.report.get("paper", {}), "title": title}
        if title == CITING:
            session.paper.references = [PaperReference(7, f"Doe, J. {CITED}. Journal of Models, 2024.")]
        session_manager.save(session)
        ids.append(sid)
    session_manager.sessions.clear()
    yield ids
    session_manager.sessions.clear()


def test_the_api_orders_the_cited_paper_first_and_explains_why(pair):
    body = client.post("/api/curriculum", json={"session_ids": pair, "today": "2026-11-20"}).json()
    assert body["status"] == "success" and [p["title"] for p in body["papers"]] == [CITED, CITING]
    assert body["citations"]["ordering"] == [{"paper": CITING, "after": CITED, "reference_number": 7, "evidence": f"Doe, J. {CITED}. Journal of Models, 2024."}]
    assert f"it cites {CITED!r} (its reference 7), which is placed before it" in body["papers"][1]["reason"] and body["shared_references"]["totals"]["total"] >= 1


def test_the_command_line_prints_the_citation_and_the_page_shows_it(pair, capsys):
    assert main(["prerequisites", "curriculum", *pair]) == 0
    out = capsys.readouterr().out
    assert f"citation: {CITING!r} cites {CITED!r} (reference 7), so it comes after it" in out
    assert "citations || {}).ordering" in PAGE.replace("(body.citations", "citations ||").replace(" ", " ") or "body.citations" in PAGE
    assert "so it comes after it." in PAGE and "shared by several of these papers" in PAGE
