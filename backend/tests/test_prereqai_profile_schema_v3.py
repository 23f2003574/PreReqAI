"""Learner profile schema 3: timestamped graded answers, lossless reading of schema 1 and 2 files, a one-time backup, bounded history, and refusal of newer or damaged files."""
import json
from datetime import datetime, timezone

import pytest

from backend import learner_profile, mastery_model, spaced_review

pytestmark = pytest.mark.prereqai

T0 = datetime(2026, 11, 23, 13, 0, 0, tzinfo=timezone.utc)
ENTRY = {"concept": "Softmax", "attempts": 4, "knew": 3, "missed": 1, "streak": 2, "last_outcome": "knew", "first_seen": "2026-11-20T10:00:00Z", "last_seen": "2026-11-22T10:00:00Z",
         "interval_hours": 72.0, "due": "2026-11-25T10:00:00Z", "graded_attempts": 4, "graded_correct": 3, "graded_streak": 2, "high_confidence_right": 2, "high_confidence_wrong": 0,
         "graded_history": ["1h", "0m", "1m", "1h"]}


def write(path, version=2, entry=ENTRY, **extra):
    path.write_text(json.dumps({"format": learner_profile.FORMAT, "schema_version": version, "known": ["Linear Algebra"], "studied": [], "quiz": {"Softmax:1": entry}, **extra}), encoding="utf-8")


def test_a_version_2_profile_is_read_without_loss(tmp_path):
    path = tmp_path / "a.json"
    write(path)
    profile, problem = learner_profile.load_full(path)
    assert problem == "" and profile["quiz"]["Softmax:1"]["graded_history"] == ["1h", "0m", "1m", "1h"] and profile["known"] == ["Linear Algebra"]
    assert profile["quiz"]["Softmax:1"]["graded_correct"] == 3 and learner_profile.SCHEMA_VERSION == 3


def test_saving_upgrades_to_version_3_and_backs_the_old_file_up_once(tmp_path):
    path = tmp_path / "a.json"
    write(path)
    original = path.read_bytes()
    profile, _ = learner_profile.load_full(path)
    learner_profile.save(path, profile["known"], profile["studied"], profile["quiz"])
    assert json.loads(path.read_text())["schema_version"] == 3
    backup = tmp_path / "a.json.v2.bak"
    assert backup.read_bytes() == original
    learner_profile.save(path, ["Calculus"], [], profile["quiz"])  # a later save never replaces the first backup
    assert backup.read_bytes() == original and not (tmp_path / "a.json.v3.bak").exists()
    assert learner_profile.load_full(path)[0]["quiz"] == profile["quiz"]


def test_a_version_1_file_is_backed_up_under_its_own_version(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"format": learner_profile.FORMAT, "schema_version": 1, "known": ["Calculus"], "studied": []}), encoding="utf-8")
    profile, _ = learner_profile.load_full(path)
    learner_profile.save(path, profile["known"], profile["studied"], profile["quiz"])
    assert (tmp_path / "old.json.v1.bak").exists() and json.loads(path.read_text())["schema_version"] == 3


def test_a_new_file_and_a_version_3_file_make_no_backup(tmp_path):
    path = tmp_path / "n.json"
    learner_profile.save(path, ["Calculus"], [], {})
    learner_profile.save(path, ["Calculus", "Statistics"], [], {})
    assert not list(tmp_path.glob("*.bak"))


def test_recording_a_graded_answer_stores_its_time_confidence_and_order(tmp_path):
    path = tmp_path / "r.json"
    learner_profile.record_quiz(path, "Softmax:1", "Softmax", "knew", T0, graded={"correct": True, "confidence": "high"})
    learner_profile.record_quiz(path, "Softmax:1", "Softmax", "missed", T0.replace(hour=14), graded={"correct": False, "confidence": "low"})
    entry = learner_profile.load_full(path)[0]["quiz"]["Softmax:1"]
    assert entry["graded_history"] == ["1h@2026-11-23T13:00:00Z", "0l@2026-11-23T14:00:00Z"]
    timed = mastery_model.decode_timed_history(entry["graded_history"])
    assert [(ok, c) for ok, c, _ in timed] == [(True, "high"), (False, "low")] and timed[1][2] == T0.replace(hour=14)
    assert mastery_model.decode_timed_history(["1h", "0m@2026-11-23T13:00:00Z", "x", "1q"])[0][2] is None


def test_history_is_bounded_and_keeps_the_most_recent_answers(tmp_path):
    path = tmp_path / "b.json"
    for n in range(spaced_review.HISTORY_LIMIT + 5):
        learner_profile.record_quiz(path, "Softmax:1", "Softmax", "knew", T0.replace(minute=n), graded={"correct": n % 2 == 0, "confidence": "medium"})
    history = learner_profile.load_full(path)[0]["quiz"]["Softmax:1"]["graded_history"]
    assert len(history) == spaced_review.HISTORY_LIMIT == 20 and history[-1].endswith("@2026-11-23T13:24:00Z")


def test_existing_mastery_is_unchanged_by_the_upgrade(tmp_path):
    path = tmp_path / "m.json"
    write(path)
    before = learner_profile.mastery(learner_profile.load_full(path)[0]["quiz"], T0)
    profile = learner_profile.load_full(path)[0]
    learner_profile.save(path, profile["known"], profile["studied"], profile["quiz"])
    assert learner_profile.mastery(learner_profile.load_full(path)[0]["quiz"], T0) == before


@pytest.mark.parametrize("version", [4, 99])
def test_a_newer_schema_is_still_refused_and_never_overwritten(tmp_path, version):
    path = tmp_path / "f.json"
    write(path, version=version)
    before = path.read_bytes()
    assert "newer PreReqAI" in learner_profile.load_full(path)[1]
    with pytest.raises(learner_profile.ProfileError):
        learner_profile.save(path, ["Calculus"], [])
    assert path.read_bytes() == before and not list(tmp_path.glob("*.bak"))


@pytest.mark.parametrize("history", [["1h@not-a-time"], ["2h"], ["1x"], "1h", [5], ["1h@2026-11-23T13:00:00Z"] * 21])
def test_damaged_history_is_refused(tmp_path, history):
    path = tmp_path / "d.json"
    write(path, version=3, entry={**ENTRY, "graded_attempts": 30, "graded_correct": 3, "graded_history": history})
    assert "invalid entry" in learner_profile.load_full(path)[1]


def test_a_corrupt_file_fails_safely_and_makes_no_backup(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("{not json", encoding="utf-8")
    assert learner_profile.load_full(path)[1]
    with pytest.raises(learner_profile.ProfileError):
        learner_profile.save(path, ["Calculus"], [])
    assert path.read_text() == "{not json" and not list(tmp_path.glob("*.bak"))


def test_a_backup_that_cannot_be_written_stops_the_save_and_keeps_the_original(tmp_path, monkeypatch):
    path = tmp_path / "e.json"
    write(path)
    original = path.read_bytes()
    profile = learner_profile.load_full(path)[0]
    monkeypatch.setattr(learner_profile.os, "replace", lambda src, dst: (_ for _ in ()).throw(OSError(13, "denied")) if str(dst).endswith(".bak") else __import__("os").rename(src, dst))
    with pytest.raises(learner_profile.ProfileError, match="backed up"):
        learner_profile.save(path, profile["known"], profile["studied"], profile["quiz"])
    assert path.read_bytes() == original
