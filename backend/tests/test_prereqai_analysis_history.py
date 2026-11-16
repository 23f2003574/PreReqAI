"""Analysis history: the listing the web page shows, reopening a saved analysis, independent deletion, damaged files and untouched learner profiles."""
import pytest
from fastapi.testclient import TestClient

from backend import learner_profile as lp
from backend.main import app
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
client = TestClient(app)


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv(lp.PROFILE_DIR_ENV, str(tmp_path / "profiles"))
    session_manager.sessions.clear()
    yield tmp_path
    session_manager.sessions.clear()


def _analyse(**options):
    return platform.analyze(SAMPLE, **options)["session_id"]


def _listing():
    return client.get("/api/session").json()


def test_several_analyses_are_listed_newest_first_with_title_date_progress_and_status(store):
    first, second = _analyse(), _analyse(studied=["Calculus"])
    body = _listing()
    assert [s["session_id"] for s in body["sessions"]] == [second, first] and body["unreadable"] == []
    newest = body["sessions"][0]
    assert newest["paper_title"].startswith("Attention Is All You Need") and isinstance(newest["created_at"], float) and newest["readiness"]
    assert newest["progress"]["completed"] == 1 and newest["progress"]["total"] >= 2 and 0 < newest["progress"]["percent"] < 100
    assert body["sessions"][1]["progress"]["completed"] == 0 and body["sessions"][1]["quiz_attempts"] == 0
    assert _listing() == body  # deterministic


def test_the_listing_follows_progress_and_quiz_answers_and_survives_a_restart(store):
    sid = _analyse()
    client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Calculus"})
    question = client.get(f"/api/session/{sid}/quiz/question", params={"concept": "Transformer"}).json()
    client.post(f"/api/session/{sid}/quiz/reveal", json={"question_id": question["question_id"]})
    client.post(f"/api/session/{sid}/quiz/outcome", json={"question_id": question["question_id"], "outcome": "knew"})
    before = _listing()["sessions"][0]
    assert before["progress"]["completed"] == 1 and before["quiz_attempts"] == 1
    session_manager.sessions.clear()  # a restart: everything is read from the saved files
    assert _listing()["sessions"][0] == before


def test_reopening_a_saved_analysis_restores_its_progress_quiz_and_settings(store):
    sid = _analyse(hours_per_day=2)
    client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Calculus"})
    question = client.get(f"/api/session/{sid}/quiz/question", params={"concept": "Transformer"}).json()
    other = _analyse()  # a later analysis
    session_manager.sessions.clear()
    reopened = client.get(f"/api/session/{sid}").json()
    assert {p["concept"]: p["completed"] for p in reopened["study_progress"]}["Calculus"] is True
    assert reopened["study_time"]["daily_hours"] == 2 and reopened["quiz_pending"][0]["question_id"] == question["question_id"]
    assert client.get(f"/api/session/{other}").json()["study_time"]["daily_hours"] == 3  # the other analysis keeps its own settings


def test_a_new_analysis_never_overwrites_an_earlier_one(store):
    first = _analyse(known=["Linear Algebra"])
    before = client.get(f"/api/session/{first}").json()
    second = _analyse()
    assert second != first and client.get(f"/api/session/{first}").json() == before
    assert {s["session_id"] for s in _listing()["sessions"]} == {first, second}


def test_deleting_one_analysis_keeps_the_others_and_every_learner_profile(store):
    lp.save(store / "profiles" / "me.json", ["Calculus"], ["Probability"])
    keep, drop = _analyse(), _analyse()
    saved = (store / "profiles" / "me.json").read_bytes()
    assert client.delete(f"/api/session/{drop}").status_code == 200
    assert [s["session_id"] for s in _listing()["sessions"]] == [keep] and client.get(f"/api/session/{drop}").status_code == 404
    assert client.get(f"/api/session/{keep}").status_code == 200 and (store / "profiles" / "me.json").read_bytes() == saved
    assert client.delete(f"/api/session/{drop}").status_code in (200, 404)  # deleting again is harmless


def test_damaged_files_are_listed_apart_without_breaking_the_history(store):
    good = _analyse()
    directory = store / "sessions"
    (directory / "deadbeef-dead-beef-dead-beefdeadbeef.session").write_bytes(b"not a session")
    body = _listing()
    assert [s["session_id"] for s in body["sessions"]] == [good] and body["unreadable"] == ["deadbeef-dead-beef-dead-beefdeadbeef"]
    assert client.get("/api/session/deadbeef-dead-beef-dead-beefdeadbeef").status_code == 404
    assert client.delete("/api/session/deadbeef-dead-beef-dead-beefdeadbeef").status_code == 200
    assert _listing()["unreadable"] == [] and not (directory / "deadbeef-dead-beef-dead-beefdeadbeef.session").exists()


def test_without_a_session_directory_only_the_running_server_sessions_are_listed(tmp_path, monkeypatch):
    monkeypatch.delenv("PREREQAI_SESSION_DIR", raising=False)
    session_manager.sessions.clear()
    sid = _analyse()
    body = _listing()
    assert [s["session_id"] for s in body["sessions"]] == [sid] and body["unreadable"] == []
    session_manager.sessions.clear()
    assert _listing()["sessions"] == []
