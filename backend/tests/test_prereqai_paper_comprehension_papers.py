"""Comprehension questions on three real benchmark papers, through the API the page calls."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform
from backend.session import session_manager
from backend.tutor import paper_quiz

pytestmark = pytest.mark.prereqai
PDFS = {name: f"backend/prereqai_eval/benchmark/pdfs/{name}.pdf" for name in ("dpo", "mixtral", "chain-of-thought")}
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def sessions(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PREREQAI_SESSION_DIR", str(tmp_path_factory.mktemp("sessions")))
        yield {name: platform.analyze(path)["session_id"] for name, path in PDFS.items()}


def test_every_paper_has_verified_claims_and_the_papers_together_cover_equation_questions(sessions):
    kinds = set()
    for name, sid in sessions.items():
        session = session_manager.get(sid)
        questions = paper_quiz.build_comprehension(session)
        pages = {p.page_number: " ".join(p.text.split()) for p in session.paper.pages}
        assert any(q["kind"] == "claim" for q in questions), name
        for q in questions:
            kinds.add(q["kind"])
            assert q["page_number"] in pages and (q["kind"] == "equation" or " ".join(q["quotation"].split()) in pages[q["page_number"]]), (name, q["question_id"])
    assert {"claim", "equation"} <= kinds


def test_the_api_serves_comprehension_questions_reveals_with_a_quotation_and_checks_the_attempt(sessions):
    sid = sessions["dpo"]
    body = client.get(f"/api/session/{sid}/paper-quiz", params={"kinds": "comprehension"}).json()
    assert body["status"] == "success" and body["questions"] and all("answer" not in q and "quotation" not in q for q in body["questions"])
    assert client.get(f"/api/session/{sid}/paper-quiz", params={"kinds": "other"}).status_code == 422
    claim = next(q for q in body["questions"] if q["kind"] == "claim")
    stored = paper_quiz.find(session_manager.get(sid), claim["question_id"])[1]
    revealed = client.post(f"/api/session/{sid}/paper-quiz/reveal", json={"question_id": claim["question_id"], "attempt": stored["answer"]}).json()
    assert revealed["attempt_correct"] is True and revealed["quotation"] == stored["quotation"] and revealed["page_number"]
    assert client.post(f"/api/session/{sid}/paper-quiz/outcome", json={"question_id": claim["question_id"], "outcome": "knew"}).status_code == 200
