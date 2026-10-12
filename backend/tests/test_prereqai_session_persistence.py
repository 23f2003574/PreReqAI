"""With PREREQAI_SESSION_DIR set, an analysed session survives a server restart."""
import pymupdf
from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager


def _upload(client, path):
    with path.open("rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()


def test_a_session_survives_a_restart_including_studied_progress_and_history(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    paper = tmp_path / "p.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 700),
                                  "1 Introduction\nA transformer uses self-attention and softmax. A policy gradient agent.\n", fontsize=10)
    doc.save(paper)
    client = TestClient(app)

    body = _upload(client, paper)
    sid = body["session_id"]
    concept = body["report"]["learning_plan"][0]["concept"]
    assert client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": concept}).status_code == 200
    assert client.post(f"/api/session/{sid}/question", json={"question": "What is attention?"}).status_code == 200

    session_manager.sessions.clear()  # the server restarts: memory is gone
    restored = client.get(f"/api/session/{sid}")
    assert restored.status_code == 200 and restored.json()["paper_title"] == body["report"]["paper"]["title"]
    assert client.post(f"/api/session/{sid}/question", json={"question": "And softmax?"}).status_code == 200
    assert session_manager.get(sid).report["readiness"]["completed_concepts"] == 1


def test_unknown_malformed_and_traversal_ids_are_just_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    (tmp_path / "secret.session").write_bytes(b"x")
    client = TestClient(app)
    for bad in ("00000000-0000-0000-0000-000000000000", "secret", "..%2F..%2Fsecret"):
        assert client.get(f"/api/session/{bad}").status_code == 404


def test_without_the_variable_nothing_is_written(tmp_path, monkeypatch):
    monkeypatch.delenv("PREREQAI_SESSION_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    session_manager.save(session_manager.create("t"))
    assert list(tmp_path.iterdir()) == []


def test_studied_matches_the_concept_name_case_insensitively_and_lists_the_plan_on_a_miss():
    client = TestClient(app)
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]

    done = client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": " probability "})
    assert done.status_code == 200 and done.json()["readiness"]["completed_concepts"] == 1

    miss = client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Graphs"})
    assert miss.status_code == 422 and "Probability" in miss.json()["detail"]


def test_a_non_model_tutor_answer_is_flagged_in_the_response_warnings():
    client = TestClient(app)
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    body = client.post(f"/api/session/{sid}/question", json={"question": "What is attention?"}).json()
    assert body["status"] == "success" and len(body["warnings"]) == 1 and "built-in" in body["warnings"][0]
    assert body["responses"][0]["supporting_concepts"]  # the useful part is still returned
