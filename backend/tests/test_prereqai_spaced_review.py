"""Learner profile schema v2: migration from v1, quiz mastery that persists across sessions and papers, the spaced-review policy and queue, and the
API, CLI and page that expose them."""
import json
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import learner_profile, spaced_review
from backend.cli import main as cli_main
from backend.main import app
from backend.platform import platform
from backend.session import session_manager
from backend.tutor import quiz_session

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
client = TestClient(app, raise_server_exceptions=False)
T0 = spaced_review.parse_time("2026-11-20T10:00:00Z")


def v1(path, known=("Linear Algebra",), studied=("Probability",)):
    path.write_text(json.dumps({"format": learner_profile.FORMAT, "schema_version": 1, "known": list(known), "studied": list(studied)}), encoding="utf-8")


# ---- the policy ----

def test_a_correct_answer_is_not_due_again_at_once_and_climbs_the_ladder():
    entry = spaced_review.update(None, "Softmax", "knew", T0)
    assert spaced_review.parse_time(entry["due"]) == T0 + timedelta(days=1)  # the first rung of the ladder, never zero
    waits = []
    for _ in range(5):
        entry = spaced_review.update(entry, "Softmax", "knew", T0)
        waits.append(entry["interval_hours"] / 24)
    assert waits == sorted(waits) and waits[-1] >= 30 and all(w > 0 for w in waits)


def test_a_missed_answer_is_due_in_hours_and_resets_the_streak():
    entry = spaced_review.update(spaced_review.update(None, "Softmax", "knew", T0), "Softmax", "knew", T0)
    missed = spaced_review.update(entry, "Softmax", "missed", T0)
    assert missed["streak"] == 0 and spaced_review.parse_time(missed["due"]) == T0 + spaced_review.MISSED_RETRY
    assert missed["interval_hours"] < entry["interval_hours"] and (missed["attempts"], missed["knew"], missed["missed"]) == (3, 2, 1)


def test_a_weak_question_comes_back_sooner_than_a_strong_one():
    strong = spaced_review.update(spaced_review.update(None, "Softmax", "knew", T0), "Softmax", "knew", T0)
    weak = {"concept": "Softmax", "attempts": 3, "knew": 1, "missed": 2, "streak": 1, "last_outcome": "knew", "first_seen": spaced_review.stamp(T0),
            "last_seen": spaced_review.stamp(T0), "interval_hours": 4, "due": spaced_review.stamp(T0)}
    weak = spaced_review.update(weak, "Softmax", "knew", T0)  # streak 2 but more misses than hits
    assert weak["interval_hours"] < strong["interval_hours"] + 1 and weak["interval_hours"] == 3 * 24 / 2


def test_the_queue_lists_due_questions_most_overdue_first_and_the_rest_as_upcoming():
    questions = {"A:1": {"concept": "A", "due": "2026-11-20T08:00:00Z", "last_outcome": "missed"},
                 "B:1": {"concept": "B", "due": "2026-11-19T10:00:00Z", "last_outcome": "knew"},
                 "C:1": {"concept": "C", "due": "2026-11-21T10:00:00Z", "last_outcome": "knew"},
                 "D:1": {"concept": "D", "due": "garbage"}}
    queue = spaced_review.queue(questions, T0)
    assert [i["question_id"] for i in queue["due"]] == ["B:1", "A:1"] and queue["due"][0]["overdue_hours"] == 24
    assert [i["question_id"] for i in queue["upcoming"]] == ["C:1"]  # an unreadable due time is skipped, not guessed
    assert {c["concept"]: c["is_due"] for c in queue["concepts"]} == {"A": True, "B": True, "C": False}


# ---- the profile: migration, persistence, protection ----

def test_a_version_1_profile_migrates_losslessly_and_keeps_its_data_when_quiz_results_arrive(tmp_path):
    path = tmp_path / "me.json"
    v1(path)
    profile, problem = learner_profile.load_full(path)
    assert problem == "" and profile == {"known": ["Linear Algebra"], "studied": ["Probability"], "quiz": {}}
    assert json.loads(path.read_text())["schema_version"] == 1  # reading does not rewrite
    learner_profile.record_quiz(path, "Softmax:1", "softmax", "knew", T0)
    saved = json.loads(path.read_text())
    assert saved["schema_version"] == 2 and saved["known"] == ["Linear Algebra"] and saved["studied"] == ["Probability"]
    assert saved["quiz"]["Softmax:1"]["concept"] == "Softmax" and saved["quiz"]["Softmax:1"]["last_outcome"] == "knew"


def test_mastery_persists_across_sessions_and_papers_and_a_progress_save_keeps_it(tmp_path):
    path = tmp_path / "me.json"
    learner_profile.record_quiz(path, "Softmax:1", "Softmax", "knew", T0)
    learner_profile.record_quiz(path, "Softmax:1", "Softmax", "knew", T0 + timedelta(days=1))
    learner_profile.save(path, ["Calculus"], ["Probability"])  # an analysis saving its progress must not drop the quiz history
    entry = learner_profile.load_full(path)[0]["quiz"]["Softmax:1"]
    assert (entry["attempts"], entry["knew"], entry["streak"]) == (2, 2, 2)
    assert learner_profile.load(path)[:2] == (["Calculus"], ["Probability"])


@pytest.mark.parametrize("text", [
    "{not json", json.dumps({"format": "x", "schema_version": 2}),
    json.dumps({"format": learner_profile.FORMAT, "schema_version": 3, "known": [], "studied": []}),
    json.dumps({"format": learner_profile.FORMAT, "schema_version": 2, "known": [], "studied": [], "quiz": {"Softmax:1": {"concept": "Softmax"}}}),
    json.dumps({"format": learner_profile.FORMAT, "schema_version": 2, "known": [], "studied": [], "quiz": []}),
])
def test_a_malformed_or_newer_profile_is_never_overwritten(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(learner_profile.ProfileError):
        learner_profile.record_quiz(path, "Softmax:1", "Softmax", "knew")
    assert path.read_text(encoding="utf-8") == text
    assert learner_profile.review_queue(path)[1] != ""


def test_invalid_outcomes_questions_and_concepts_are_refused_without_a_write(tmp_path):
    path = tmp_path / "me.json"
    for args in (("Softmax:1", "Softmax", "maybe"), ("Softmax", "Softmax", "knew"), ("Softmax:1", "No Such Concept", "knew")):
        with pytest.raises(learner_profile.ProfileError):
            learner_profile.record_quiz(path, *args)
    assert not path.exists()


def test_a_save_whose_readback_fails_leaves_the_valid_profile_alone(tmp_path, monkeypatch):
    path = tmp_path / "me.json"
    learner_profile.record_quiz(path, "Softmax:1", "Softmax", "knew", T0)
    before, quiz = path.read_text(), learner_profile.load_full(path)[0]["quiz"]
    monkeypatch.setattr(learner_profile, "parse_full", lambda raw: {"known": [], "studied": [], "quiz": {}})  # a faulty rewrite that loses the history
    with pytest.raises(learner_profile.ProfileError):
        learner_profile.save(path, ["Calculus"], [], quiz)
    assert path.read_text() == before and not list(tmp_path.glob(".*tmp"))


# ---- the API, the quiz workflow, the CLI and the page ----

@pytest.fixture
def served(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("PREREQAI_PROFILE_DIR", str(tmp_path / "profiles"))
    monkeypatch.delenv("PREREQAI_TUTOR_PROVIDER", raising=False)
    session_manager.sessions.clear()
    yield tmp_path
    session_manager.sessions.clear()


def analyse(profile="me"):
    with open(SAMPLE, "rb") as handle:
        body = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, data={"profile": profile}).json()
    assert body["status"] == "success"
    return body["session_id"]


def answer(sid, outcome):
    asked = client.get(f"/api/session/{sid}/quiz/question").json()
    identifier = asked["question_id"]
    client.post(f"/api/session/{sid}/quiz/reveal", json={"question_id": identifier})
    return identifier, client.post(f"/api/session/{sid}/quiz/outcome", json={"question_id": identifier, "outcome": outcome}).json()


def test_a_quiz_outcome_is_remembered_in_the_profile_and_reviewed_across_papers(served):
    sid = analyse()
    identifier, body = answer(sid, "missed")
    assert body["status"] == "success" and body["review"]["saved"] is True and body["review"]["interval_hours"] == 4
    queue = client.get("/api/review", params={"profile": "me"}).json()
    assert queue["status"] == "success" and queue["due"] == [] and queue["upcoming"][0]["question_id"] == identifier  # 4 hours away
    later = learner_profile.review_queue(served / "profiles" / "me.json", spaced_review.now() + timedelta(hours=5))[0]
    assert [i["question_id"] for i in later["due"]] == [identifier]
    second = analyse()  # another paper session, same profile: the history is still there
    assert second != sid and client.get("/api/review", params={"profile": "me"}).json()["upcoming"][0]["question_id"] == identifier


def test_review_api_errors_are_clear_and_a_profile_free_session_still_quizzes(served, monkeypatch):
    assert client.get("/api/review", params={"profile": "../x"}).status_code == 422
    (served / "profiles").mkdir()
    (served / "profiles" / "broken.json").write_text("{nope", encoding="utf-8")
    assert client.get("/api/review", params={"profile": "broken"}).status_code == 409
    assert (served / "profiles" / "broken.json").read_text() == "{nope"
    monkeypatch.delenv("PREREQAI_PROFILE_DIR")
    assert client.get("/api/review").status_code == 404
    session_manager.sessions.clear()
    sid = platform.analyze(SAMPLE)["session_id"]
    _, body = answer(sid, "knew")
    assert body["status"] == "success" and "review" not in body  # no profile, no review data, the quiz is unchanged


def test_the_cli_lists_the_due_reviews(tmp_path, capsys):
    path = tmp_path / "me.json"
    learner_profile.record_quiz(path, "Softmax:1", "Softmax", "missed", spaced_review.now() - timedelta(days=1))
    assert cli_main(["prerequisites", "review", "--profile", str(path)]) == 0
    assert "1 question(s) due" in capsys.readouterr().out
    assert cli_main(["prerequisites", "review", "--profile", str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["due"][0]["question_id"] == "Softmax:1"
    path.write_text("{bad", encoding="utf-8")
    assert cli_main(["prerequisites", "review", "--profile", str(path)]) == 1 and path.read_text() == "{bad"


def test_the_page_has_the_review_queue_wired_to_the_api():
    assert 'id="reviewBtn"' in PAGE and 'id="reviewList"' in PAGE and "/api/review" in PAGE and "loadReviews" in PAGE
