"""The optional persistent learner profile: storage, validation, CLI --profile, the server's profile directory, and unchanged behaviour without it."""
import json
import os

import pytest
from fastapi.testclient import TestClient

from backend import cli, learner_profile as lp
from backend.main import app
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _analyze(capsys, *args):
    assert cli.main(["prerequisites", "analyze", SAMPLE, "--json", *args]) == 0
    return json.loads(capsys.readouterr().out)


def _plan(outcome):
    return {item["concept"]: item["completed"] for item in outcome["report"]["study_progress"]}


def test_a_profile_is_created_and_loaded_with_the_documented_envelope(tmp_path):
    path = tmp_path / "me.json"
    lp.save(path, ["linear-algebra"], ["Probability"])
    data = json.loads(path.read_text())
    assert data == {"format": "prereqai-learner-profile", "schema_version": 3, "known": ["linear-algebra"], "studied": ["Probability"], "quiz": {}}
    assert lp.load(path) == (["Linear Algebra"], ["Probability"], "")  # read back in PreReqAI's own spelling


def test_known_and_studied_survive_a_restart_and_a_second_paper_reuses_them(tmp_path, capsys):
    profile = str(tmp_path / "p.json")
    first = _analyze(capsys, "--profile", profile, "--known", "Linear Algebra", "--studied", "Probability")
    assert first["profile"]["known"] == ["Linear Algebra"] and first["profile"]["studied"] == ["Probability"]
    second = _analyze(capsys, "--profile", profile)  # a new run, no explicit knowledge
    plan = _plan(second)
    assert "Linear Algebra" not in plan and plan["Probability"] is True and second["profile"]["known"] == ["Linear Algebra"]
    assert not any("is not in this paper's study plan" in w for w in second["warnings"])


def test_without_a_profile_nothing_changes(tmp_path, capsys):
    outcome = _analyze(capsys, "--known", "Linear Algebra")
    assert "profile" not in outcome and "Linear Algebra" not in _plan(outcome)
    assert list(tmp_path.iterdir()) == []


def test_precedence_explicit_values_add_known_wins_and_nothing_is_removed(tmp_path):
    path = tmp_path / "p.json"
    lp.save(path, ["Calculus"], ["Probability", "Optimization"])
    run = lp.ProfileRun(path, ["Probability", "Statistics"], ["Graphs"])
    assert run.known == ["Calculus", "Probability", "Statistics"]  # the profile first, then explicit; a subject given as known leaves studied
    assert "Probability" not in run.studied and run.studied == ["Optimization", "Graphs"]
    run.finish({"status": "success", "report": {"study_progress": []}, "warnings": []})
    known, studied, _ = lp.load(path)
    assert known == ["Calculus", "Probability", "Statistics"] and studied == ["Optimization", "Graphs"]  # Optimization was kept


def test_a_missing_profile_is_empty_and_created_on_success(tmp_path):
    path = tmp_path / "new" / "p.json"
    assert lp.load(path) == ([], [], "")
    outcome = lp.ProfileRun(path, [], ["Probability"]).finish({"status": "success", "report": {"study_progress": [{"concept": "Calculus", "completed": True}]}, "warnings": []})
    assert outcome["profile"]["studied"] == ["Probability", "Calculus"] and path.exists()


@pytest.mark.parametrize("raw", [b"{broken", b"[1, 2]", b'{"format": "other", "schema_version": 1}', b'{"format": "prereqai-learner-profile", "schema_version": 99}',
                                 b'{"format": "prereqai-learner-profile", "schema_version": 1, "known": "Calculus"}',
                                 b'{"format": "prereqai-learner-profile", "schema_version": 1, "known": [1]}',
                                 b'{"format": "prereqai-learner-profile", "schema_version": 1, "known": [NaN]}', b"\xff\xfe"])
def test_a_corrupt_or_unsupported_profile_warns_and_is_never_overwritten(tmp_path, raw, capsys):
    path = tmp_path / "p.json"
    path.write_bytes(raw)
    outcome = _analyze(capsys, "--profile", str(path), "--known", "Calculus")
    assert path.read_bytes() == raw  # untouched, so the learner can repair it
    assert any("left unchanged" in w for w in outcome["warnings"]) and any("was not updated" in w for w in outcome["warnings"])
    assert "profile" not in outcome and "Calculus" not in _plan(outcome)  # still analysed with the explicit values


def test_duplicates_are_stored_once_whatever_their_spelling(tmp_path):
    path = tmp_path / "p.json"
    lp.save(path, ["Linear Algebra", "linear_algebra", "LINEAR  ALGEBRA", "Calculus"], ["calculus", "Probability", "probability"])
    assert lp.load(path)[:2] == (["Linear Algebra", "Calculus"], ["Probability"])


def test_unknown_names_are_not_saved_and_ones_already_in_a_file_are_kept(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"format": lp.FORMAT, "schema_version": 1, "known": ["Obsolete Concept"], "studied": []}))
    outcome = lp.ProfileRun(path, ["Quantum Gravity", "Calculus"], []).finish({"status": "success", "report": {"study_progress": []}, "warnings": []})
    assert any("'Quantum Gravity' is not a subject PreReqAI knows" in w for w in outcome["warnings"])
    assert json.loads(path.read_text())["known"] == ["Obsolete Concept", "Calculus"]  # the old entry is kept, the unknown request is not added


def test_an_interrupted_write_keeps_the_previous_profile(tmp_path, monkeypatch):
    path = tmp_path / "p.json"
    lp.save(path, ["Calculus"], [])
    before = path.read_bytes()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        lp.save(path, ["Calculus", "Probability"], [])
    assert path.read_bytes() == before and [p.name for p in tmp_path.iterdir()] == ["p.json"]  # no temporary file is left
    outcome = lp.ProfileRun(path, ["Graphs"], []).finish({"status": "success", "report": {"study_progress": []}, "warnings": []})
    assert any("previous profile is unchanged" in w for w in outcome["warnings"]) and "profile" not in outcome


client = TestClient(app)


def _post(**data):
    with open(SAMPLE, "rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, data=data).json()


def test_the_api_ignores_profiles_unless_a_directory_is_configured(tmp_path, monkeypatch):
    monkeypatch.delenv(lp.PROFILE_DIR_ENV, raising=False)
    session_manager.sessions.clear()
    body = _post(profile="me", known="Linear Algebra")
    assert body["status"] == "success" and "profile" not in body and any("profiles are off" in w for w in body["warnings"])
    assert "Linear Algebra" not in {s["concept"] for s in body["report"]["study_progress"]}
    assert not any(tmp_path.iterdir())


def test_the_api_keeps_each_named_profile_separate_and_reuses_it(tmp_path, monkeypatch):
    monkeypatch.setenv(lp.PROFILE_DIR_ENV, str(tmp_path))
    session_manager.sessions.clear()
    first = _post(profile="alice", known="Linear Algebra", studied="Probability")
    assert first["profile"]["known"] == ["Linear Algebra"] and (tmp_path / "alice.json").exists()
    again = _post(profile="alice")
    assert {s["concept"]: s["completed"] for s in again["report"]["study_progress"]}["Probability"] is True
    other = _post(profile="bob")
    assert other["profile"]["known"] == [] and "Linear Algebra" in {s["concept"] for s in other["report"]["study_progress"]}  # not mixed
    default = _post()
    assert default["profile"]["path"].endswith("default.json")
    bad = client.post("/api/prerequisites/analyze", data={"source": "10.1145/3292500.3330701", "profile": "../etc"})
    assert bad.status_code == 422 and "Invalid `profile`" in bad.json()["detail"]
    session_manager.sessions.clear()
