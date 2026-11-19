"""Learner profile management: list, show, change, forget, export/import, atomic writes, schema v1/v2 compatibility and isolation, through the API, CLI and page."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import learner_profile as lp
from backend.cli import main as cli_main
from backend.main import app
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
SAMPLE = "examples/prerequisites/sample-paper.pdf"
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def profiles(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_PROFILE_DIR", str(tmp_path / "profiles"))
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    session_manager.sessions.clear()
    yield tmp_path / "profiles"
    session_manager.sessions.clear()


def patch(name, **body):
    return client.patch(f"/api/profiles/{name}", json=body)


def test_listing_showing_and_changing_a_profile(profiles):
    assert client.get("/api/profiles").json()["profiles"] == []
    body = patch("me", add_known=["linear-algebra"], add_studied=["Probability", "calculus"]).json()
    assert body["status"] == "success" and (body["known"], body["studied"]) == (["Linear Algebra"], ["Probability", "Calculus"]) and body["mastery"] == []
    lp.record_quiz(profiles / "me.json", "Softmax:1", "Softmax", "missed")
    shown = client.get("/api/profiles/me").json()
    assert shown["mastery"][0]["concept"] == "Softmax" and shown["mastery"][0]["status"] == "needs_practice" and shown["schema_version"] == 2
    assert shown["reviews"]["upcoming"][0]["question_id"] == "Softmax:1"
    listed = client.get("/api/profiles").json()["profiles"]
    assert listed == [{"name": "me", "readable": True, "known": 1, "studied": 2, "questions": 1, "due": 0}]
    assert client.get("/api/profiles/nobody").status_code == 404


def test_known_wins_and_forgetting_removes_concepts_from_later_plans_but_keeps_mastery(profiles):
    patch("me", add_known=["Linear Algebra"], add_studied=["Probability"])
    again = patch("me", add_studied=["Linear Algebra"]).json()
    assert again["known"] == ["Linear Algebra"] and "Linear Algebra" not in again["studied"] and "already known" in again["warnings"][0]
    lp.record_quiz(profiles / "me.json", "Softmax:1", "Softmax", "knew")
    with open(SAMPLE, "rb") as handle:
        plan_with = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, data={"profile": "me"}).json()
    steps = [s["concept"] for s in plan_with["report"]["learning_plan"]]
    assert "Linear Algebra" not in steps
    after = patch("me", forget=["linear algebra"]).json()
    assert after["known"] == [] and after["mastery"][0]["concept"] == "Softmax"  # forgetting knowledge does not reset mastery
    with open(SAMPLE, "rb") as handle:
        plan_after = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, data={"profile": "me"}).json()
    assert "Linear Algebra" in [s["concept"] for s in plan_after["report"]["learning_plan"]]  # it shapes the next plan again: it is back
    wiped = patch("me", forget_quiz=["Softmax"]).json()
    assert wiped["mastery"] == [] and wiped["studied"]  # only the history went


def test_invalid_names_and_payloads_are_refused_without_a_write(profiles):
    assert patch("me", add_known=["Linear Algebra"]).status_code == 200
    before = (profiles / "me.json").read_text()
    for body in ({"add_known": ["Astrology"]}, {"forget": ["Linear Algebra", "Nonsense"]}, {"add_known": [""]}, {"add_known": ["x" * 300]}, {"add_known": ["Calculus"] * 201}):
        response = patch("me", **body)
        assert response.status_code == 422, body
    assert "Astrology" in patch("me", add_known=["Astrology"]).json()["detail"] and (profiles / "me.json").read_text() == before
    assert client.patch("/api/profiles/me", json={"add_known": "Calculus"}).status_code == 422
    assert patch("a.b", add_known=["Calculus"]).status_code == 422 and patch("a b", add_known=["Calculus"]).status_code == 422
    assert client.get("/api/profiles/bad%20name").status_code == 422


def test_an_unreadable_or_newer_profile_is_reported_and_never_changed(profiles):
    profiles.mkdir()
    for name, text in {"broken": "{nope", "newer": json.dumps({"format": lp.FORMAT, "schema_version": 9, "known": [], "studied": []})}.items():
        (profiles / f"{name}.json").write_text(text, encoding="utf-8")
        assert patch(name, add_known=["Calculus"]).status_code == 409 and client.get(f"/api/profiles/{name}").status_code == 409
        assert client.get(f"/api/profiles/{name}/export").status_code == 409 and (profiles / f"{name}.json").read_text() == text
    listed = {p["name"]: p for p in client.get("/api/profiles").json()["profiles"]}
    assert listed["broken"]["readable"] is False and "problem" in listed["broken"]


def test_export_and_import_round_trip_with_v1_and_replace_protection(profiles):
    patch("me", add_known=["Calculus"])
    lp.record_quiz(profiles / "me.json", "Softmax:1", "Softmax", "knew")
    exported = client.get("/api/profiles/me/export")
    assert "attachment" in exported.headers["content-disposition"] and exported.json()["schema_version"] == 2 and exported.json()["quiz"]["Softmax:1"]["knew"] == 1
    imported = client.post("/api/profiles/copy/import", content=exported.content)
    assert imported.status_code == 200 and imported.json()["known"] == ["Calculus"] and imported.json()["mastery"][0]["concept"] == "Softmax"
    assert client.post("/api/profiles/copy/import", content=exported.content).status_code == 409  # not overwritten by accident
    assert client.post("/api/profiles/copy/import", content=exported.content, params={"replace": "true"}).status_code == 200
    v1 = json.dumps({"format": lp.FORMAT, "schema_version": 1, "known": ["Linear Algebra"], "studied": ["Probability"]})
    legacy = client.post("/api/profiles/old/import", content=v1).json()
    assert (legacy["known"], legacy["studied"], legacy["mastery"]) == (["Linear Algebra"], ["Probability"], [])
    assert json.loads((profiles / "old.json").read_text())["schema_version"] == 2
    for bad in (b"{nope", json.dumps({"format": "x"}).encode(), json.dumps({"format": lp.FORMAT, "schema_version": 3, "known": [], "studied": []}).encode()):
        assert client.post("/api/profiles/bad/import", content=bad).status_code == 422
    assert not (profiles / "bad.json").exists()


def test_a_failed_write_keeps_the_previous_profile(profiles, monkeypatch):
    patch("me", add_known=["Calculus"])
    before = (profiles / "me.json").read_text()
    monkeypatch.setattr(lp.os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError(28, "No space left on device")))
    response = patch("me", add_known=["Probability"])
    assert response.status_code == 500 and "previous profile is unchanged" in response.json()["detail"]
    assert (profiles / "me.json").read_text() == before and not list(profiles.glob(".*tmp"))


def test_profiles_are_isolated_and_delete_needs_confirmation(profiles):
    patch("alice", add_known=["Calculus"])
    patch("bob", add_known=["Probability"])
    assert client.get("/api/profiles/alice").json()["known"] == ["Calculus"] and client.get("/api/profiles/bob").json()["known"] == ["Probability"]
    assert client.delete("/api/profiles/alice").status_code == 422 and (profiles / "alice.json").exists()
    assert client.delete("/api/profiles/alice", params={"confirm": "true"}).json()["deleted"] is True and not (profiles / "alice.json").exists()
    assert (profiles / "bob.json").exists() and client.delete("/api/profiles/alice", params={"confirm": "true"}).status_code == 404


def test_profiles_are_off_without_a_directory(monkeypatch):
    monkeypatch.delenv("PREREQAI_PROFILE_DIR", raising=False)
    assert client.get("/api/profiles").status_code == 404 and patch("me", add_known=["Calculus"]).status_code == 404


def test_the_cli_shows_changes_and_exports_the_same_profile(tmp_path, capsys):
    path = tmp_path / "me.json"
    assert cli_main(["prerequisites", "profile", str(path), "--known", "linear algebra", "--studied", "Probability"]) == 0
    assert "known: Linear Algebra" in capsys.readouterr().out
    assert cli_main(["prerequisites", "profile", str(path), "--forget", "Linear Algebra", "--json"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["known"] == [] and document["studied"] == ["Probability"] and document["schema_version"] == 2
    assert cli_main(["prerequisites", "profile", str(path), "--known", "Astrology"]) == 2 and json.loads(path.read_text())["studied"] == ["Probability"]
    path.write_text("{nope", encoding="utf-8")
    assert cli_main(["prerequisites", "profile", str(path), "--known", "Calculus"]) == 1 and path.read_text() == "{nope"


def test_a_v1_profile_is_read_by_the_api_without_losing_anything(profiles):
    profiles.mkdir()
    (profiles / "old.json").write_text(json.dumps({"format": lp.FORMAT, "schema_version": 1, "known": ["Calculus"], "studied": ["Probability"]}), encoding="utf-8")
    assert client.get("/api/profiles/old").json()["known"] == ["Calculus"]
    assert json.loads((profiles / "old.json").read_text())["schema_version"] == 1  # reading never rewrites
    patch("old", add_studied=["Statistics"])
    saved = json.loads((profiles / "old.json").read_text())
    assert saved["schema_version"] == 2 and saved["known"] == ["Calculus"] and saved["studied"] == ["Probability", "Statistics"]


def test_the_page_can_show_and_edit_the_profile():
    for marker in ('id="profileBtn"', 'id="profileKnown"', 'id="profileStudied"', 'id="profileExport"', "/api/profiles/", '"PATCH"', "Forget", "renderProfile"):
        assert marker in PAGE
