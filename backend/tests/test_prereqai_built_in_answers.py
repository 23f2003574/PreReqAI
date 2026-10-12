"""Questions over HTTP are answered from the analysis (definitions, prerequisite reasons), not a bare placeholder."""
import pymupdf
from starlette.testclient import TestClient

from backend.main import app


def _session(tmp_path, text):
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 760), text, fontsize=10)
    doc.save(path)
    client = TestClient(app)
    with open(path, "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    return client, sid


def test_why_do_i_need_a_prerequisite_is_answered_with_its_justification(tmp_path):
    client, sid = _session(tmp_path, "Abstract\nWe train a policy gradient agent over a Markov decision process.\n")
    body = client.post(f"/api/session/{sid}/question", json={"question": "Why do I need calculus?"}).json()
    assert body["status"] == "success"
    answer = body["responses"][0]["answer"]
    assert "derivatives" in answer and "tutoring model has not" not in answer
    assert body["responses"][0]["confidence"] > 0
    assert "not generated" in body["warnings"][0]  # still disclosed: no model is behind it


def test_what_is_a_concept_is_answered_with_its_definition(tmp_path):
    client, sid = _session(tmp_path, "Abstract\nWe train a policy gradient agent over a Markov decision process.\n")
    body = client.post(f"/api/session/{sid}/question", json={"question": "What is policy gradient?"}).json()
    assert body["responses"][0]["answer"].startswith("Policy Gradient:")


def test_an_unrelated_question_keeps_the_disclosed_placeholder(tmp_path):
    client, sid = _session(tmp_path, "Abstract\nWe train a policy gradient agent over a Markov decision process.\n")
    body = client.post(f"/api/session/{sid}/question", json={"question": "hello"}).json()
    assert "tutoring model has not" in body["responses"][0]["answer"]
    assert "placeholder" in body["warnings"][0]


def test_identical_workflow_answers_are_returned_once(tmp_path):
    client, sid = _session(tmp_path, "Abstract\nWe train a policy gradient agent over a Markov decision process.\n")
    body = client.post(f"/api/session/{sid}/question", json={"question": "What is policy gradient?"}).json()
    answers = [r["answer"] for r in body["responses"]]
    assert len(answers) == len(set(answers)) == 1
    assert client.get(f"/api/session/{sid}").status_code == 200
