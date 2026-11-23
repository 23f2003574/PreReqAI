"""Plans consume decayed profile evidence, and repeated requests do not re-parse an unchanged profile: the parsed profile is cached on file metadata and every change invalidates it."""
import json
import os
from datetime import timedelta
from types import SimpleNamespace

import pytest

from backend import adaptive_plan, learner_profile, spaced_review
from backend.tests.test_prereqai_adaptive_profile import adjustment, entries, report

pytestmark = pytest.mark.prereqai


@pytest.fixture(autouse=True)
def fresh_cache():
    learner_profile.clear_cache()
    yield
    learner_profile.clear_cache()


def write(path, quiz, known=()):
    learner_profile.save(path, list(known), [], quiz)


def test_an_unchanged_profile_is_parsed_once(tmp_path):
    path = tmp_path / "me.json"
    write(path, entries("Calculus"))
    before = dict(learner_profile.cache_stats)
    first, _ = learner_profile.load_cached(path)
    for _ in range(5):
        again, problem = learner_profile.load_cached(path)
        assert problem == "" and again == first
    assert learner_profile.cache_stats["parses"] - before["parses"] == 1 and learner_profile.cache_stats["hits"] - before["hits"] == 5


def test_a_save_or_an_outside_edit_makes_the_next_read_parse_again(tmp_path):
    path = tmp_path / "me.json"
    write(path, entries("Calculus"), ["Linear Algebra"])
    assert learner_profile.load_cached(path)[0]["known"] == ["Linear Algebra"]
    write(path, entries("Calculus"), ["Calculus"])
    assert learner_profile.load_cached(path)[0]["known"] == ["Calculus"]
    data = json.loads(path.read_text())
    data["known"] = ["Probability"]
    path.write_text(json.dumps(data), encoding="utf-8")  # an edit by hand, keeping the size the same is not required: the modification time moves
    os.utime(path, ns=(10**18, 10**18))
    assert learner_profile.load_cached(path)[0]["known"] == ["Probability"]


def test_callers_get_their_own_copy(tmp_path):
    path = tmp_path / "me.json"
    write(path, entries("Calculus"))
    first, _ = learner_profile.load_cached(path)
    first["quiz"].clear()
    first["known"].append("Nothing")
    again, _ = learner_profile.load_cached(path)
    assert again["quiz"] and "Nothing" not in again["known"]


def test_missing_unreadable_and_damaged_files_are_never_cached(tmp_path):
    path = tmp_path / "me.json"
    assert learner_profile.load_cached(path) == ({"known": [], "studied": [], "quiz": {}}, "")
    path.write_text("{not json", encoding="utf-8")
    assert learner_profile.load_cached(path)[1] and learner_profile.load_cached(path)[1]
    path.unlink()
    write(path, entries("Calculus"))
    assert learner_profile.load_cached(path)[1] == "" and learner_profile.load_cached(path)[0]["quiz"]


def test_the_cache_is_bounded(tmp_path):
    for n in range(learner_profile._CACHE_LIMIT + 5):
        path = tmp_path / f"p{n}.json"
        write(path, {})
        learner_profile.load_cached(path)
    assert len(learner_profile._cache) <= learner_profile._CACHE_LIMIT


def session_for(tmp_path, monkeypatch, name="me"):
    monkeypatch.setenv(learner_profile.PROFILE_DIR_ENV, str(tmp_path))
    return SimpleNamespace(profile=name, report=report(), quiz_attempts=[])


def test_repeated_plan_requests_read_the_profile_once_and_agree(tmp_path, monkeypatch):
    write(tmp_path / "me.json", entries("Calculus"))
    session = session_for(tmp_path, monkeypatch)
    before = learner_profile.cache_stats["parses"]
    plans = [adaptive_plan.session_report(session)["learning_plan"] for _ in range(4)]
    assert all(plan == plans[0] for plan in plans) and learner_profile.cache_stats["parses"] - before == 1
    assert next(s for s in plans[0] if s["concept"] == "Calculus")["estimated_hours"] == 1.2


def test_a_profile_change_reaches_the_next_plan_without_a_restart(tmp_path, monkeypatch):
    path = tmp_path / "me.json"
    write(path, entries("Calculus"))
    session = session_for(tmp_path, monkeypatch)
    assert adaptive_plan.session_report(session)["learning_plan"][0]["estimated_hours"] == 1.2
    write(path, entries("Calculus", last_outcome="missed"))
    assert adaptive_plan.session_report(session)["learning_plan"][0]["estimated_hours"] == 4.0


def test_stale_mastery_does_not_shorten_a_new_papers_plan_and_fresh_mastery_does(tmp_path, monkeypatch):
    path = tmp_path / "me.json"
    session = session_for(tmp_path, monkeypatch)
    write(path, entries("Calculus", seen_days_ago=60))
    assert adaptive_plan.session_report(session)["learning_plan"][0]["estimated_hours"] == 4.0
    assert adjustment(adaptive_plan.propose(report(), [], None, None, learner_profile.load_cached(path)[0]["quiz"]), "Calculus") is None
    write(path, entries("Calculus", seen_days_ago=1))
    assert adaptive_plan.session_report(session)["learning_plan"][0]["estimated_hours"] == 1.2


def test_adaptation_stays_reversible_and_explained_and_a_session_without_a_profile_is_unchanged(tmp_path, monkeypatch):
    write(tmp_path / "me.json", entries("Calculus"))
    session = session_for(tmp_path, monkeypatch)
    session.report = {**report(), "adaptive_overrides": {"Calculus": "reject"}}
    assert adaptive_plan.session_report(session)["learning_plan"][0]["estimated_hours"] == 4.0
    session.report = report()
    change = adjustment(adaptive_plan.propose(session.report, [], None, None, adaptive_plan.profile_quiz(session)), "Calculus")
    assert change["evidence"]["source"] == "profile" and "learner profile" in change["reason"]
    assert adaptive_plan.session_report(SimpleNamespace(profile=None, report=report(), quiz_attempts=[])) == report()
