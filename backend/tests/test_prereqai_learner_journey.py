"""Acceptance: one learner's whole journey over the public HTTP API, in order -- personalised upload, a question,
progress up and back down, a failed upload in the middle, then discarding the paper."""
import pymupdf
from starlette.testclient import TestClient

from backend.main import app

TEXT = "Abstract\nWe train a policy gradient agent over a Markov decision process, with a transformer encoder.\n"


def _paper(tmp_path):
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 760), TEXT, fontsize=10)
    doc.save(path)
    return path.read_bytes()


def test_a_learner_prepares_for_a_paper_end_to_end(tmp_path):
    client = TestClient(app)
    pdf = _paper(tmp_path)

    # 1. upload, saying what is already known and what has been studied
    created = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", pdf, "application/pdf")},
                          data={"known": ["Linear Algebra"], "studied": ["Probability"]})
    assert created.status_code == 200
    body = created.json()
    sid, report = body["session_id"], body["report"]
    plan = [step["concept"] for step in report["learning_plan"]]
    assert "Linear Algebra" not in plan and {"Probability", "Calculus"} <= set(plan)
    assert report["readiness"]["completed_concepts"] == 1 and not report["readiness"]["ready_to_read"]
    assert report["paper_difficulty"]["explanation"].startswith(f"{len(plan)} prerequisite concepts")

    # 2. the session is listed and a question gets a disclosed built-in answer
    assert sid in [s["session_id"] for s in client.get("/api/session").json()["sessions"]]
    answer = client.post(f"/api/session/{sid}/question", json={"question": "Why do I need calculus?"}).json()
    assert len(answer["responses"]) == 1 and "derivatives" in answer["responses"][0]["answer"]
    assert "not generated" in answer["warnings"][0]

    # 3. a bad upload in the middle fails cleanly and leaves this session and the listing alone
    sessions_before = len(client.get("/api/session").json()["sessions"])
    broken = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", b"%PDF-1.4 garbage", "application/pdf")})
    assert broken.status_code == 400 and broken.json()["status"] == "failure"
    assert len(client.get("/api/session").json()["sessions"]) == sessions_before
    assert client.get(f"/api/session/{sid}").json()["readiness"]["completed_concepts"] == 1

    # 4. finishing the plan makes the paper ready; undoing a step takes that back
    for concept in plan:
        client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": concept})
    assert client.get(f"/api/session/{sid}").json()["readiness"]["ready_to_read"] is True
    undone = client.request("DELETE", f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Calculus"})
    assert undone.status_code == 200 and undone.json()["readiness"]["ready_to_read"] is False
    assert client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Linear Algebra"}).status_code == 422  # known, not planned

    # 5. discarding the paper removes the session everywhere
    assert client.delete(f"/api/session/{sid}").status_code == 200
    assert client.get(f"/api/session/{sid}").status_code == 404
    assert sid not in [s["session_id"] for s in client.get("/api/session").json()["sessions"]]
    assert client.post(f"/api/session/{sid}/question", json={"question": "hello"}).status_code == 404
