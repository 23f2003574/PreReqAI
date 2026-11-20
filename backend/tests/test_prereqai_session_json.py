"""Saved sessions are a versioned JSON envelope: faithful round trips, migration of older pickle files, atomic writes, and safe refusal of bad files."""
import json
import math
import pickle
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import Prerequisite
from backend.platform import platform
from backend.session import session_codec, session_manager
from backend.session.session_codec import SessionFormatError
from backend.session.session_manager import SessionManager

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def saved(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    sid = platform.analyze(SAMPLE, hours_per_day=4)["session_id"]
    yield sid, tmp_path / f"{sid}.session"
    session_manager.sessions.clear()


def reload(sid):
    session_manager.sessions.clear()  # a restart: only the file remains
    return session_manager.get(sid)


def edit_json(path, change):
    envelope = json.loads(path.read_bytes())
    change(envelope)
    path.write_text(json.dumps(envelope), encoding="utf-8")
    session_manager.sessions.clear()


def use(sid, answer_question=True):
    """A session with every kind of learner state: studied, known, daily hours, quiz attempts and a conversation."""
    client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Probability"})
    client.post(f"/api/prerequisites/sessions/{sid}/known", params={"concept": "Calculus"})
    question = client.get(f"/api/session/{sid}/quiz/question", params={"concept": "Softmax"}).json()["question_id"]
    client.post(f"/api/session/{sid}/quiz/outcome", json={"question_id": question, "outcome": "knew"})
    if answer_question:
        client.post(f"/api/session/{sid}/question", json={"question": "What should I learn first?"})


def test_the_file_is_a_documented_versioned_json_envelope_and_not_a_pickle(saved):
    sid, path = saved
    envelope = json.loads(path.read_bytes())
    assert envelope["format"] == "prereqai-session" and envelope["schema_version"] == SessionManager.SCHEMA_VERSION == 5
    assert envelope["session"]["__t__"] == "dc" and envelope["session"]["c"] == "backend.session.learning_session.LearningSession"
    assert path.read_bytes()[:1] == b"{" and b"\x80" not in path.read_bytes()[:2]


def test_a_session_with_progress_known_concepts_settings_quiz_and_history_reloads_equivalent(saved):
    sid, path = saved
    use(sid)
    before = session_manager.get(sid)
    expected = session_codec.encode(before)
    after = reload(sid)
    assert after is not before and session_codec.encode(after) == expected  # every attribute, deeply
    assert after.paper.hours_per_day == 4 and after.paper.study_time.daily_hours == 4 and after.conversation_history
    assert {item.concept for item in after.paper.study_progress if item.completed} == {"Probability"}
    assert after.quiz_attempts[0]["outcome"] == "knew" and "Calculus" not in [step.concept for step in after.paper.learning_plan]
    body = client.get(f"/api/session/{sid}").json()
    assert body["study_time"]["daily_hours"] == 4.0 and body["readiness"]["completed_concepts"] == 1
    plan = client.get(f"/api/session/{sid}/plan").text  # and resuming from the saved plan keeps the same state
    resumed = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", Path(SAMPLE).read_bytes(), "application/pdf"),
                                                              "resume": ("plan.md", plan.encode())}).json()["report"]
    assert resumed["study_time"]["daily_hours"] == 4.0 and "Calculus" not in [s["concept"] for s in resumed["learning_plan"]]


def test_the_codec_round_trips_every_container_and_rejects_what_it_cannot_hold():
    value = {"t": (1, "a"), "s": {3, 1}, "f": frozenset({"x"}), "d": {1: "one", ("k", 2): [None, True]}, "n": math.nan, "i": -math.inf, "l": [1.5, "é"],
             "tag": {"__t__": "not a tag"}, "p": Prerequisite(concept="Calculus", reason="r", confidence=0.5)}
    again = session_codec.decode(json.loads(json.dumps(session_codec.encode(value))))
    assert math.isnan(again.pop("n")) and again.pop("i") == -math.inf
    expected = {k: v for k, v in value.items() if k not in ("n", "i")}
    assert again == expected and isinstance(again["t"], tuple) and isinstance(again["s"], set) and isinstance(again["f"], frozenset)
    with pytest.raises(TypeError):
        session_codec.encode({"x": object()})
    cycle = []
    cycle.append(cycle)
    with pytest.raises(SessionFormatError, match="refers to itself"):
        session_codec.encode(cycle)


def test_older_pickle_sessions_migrate_to_json_keeping_the_learners_progress(saved):
    sid, path = saved
    use(sid, answer_question=False)
    legacy = session_manager.get(sid)
    legacy.schema_version = 3
    path.write_bytes(pickle.dumps(legacy))  # exactly what a version-3 server left behind
    legacy.schema_version = SessionManager.SCHEMA_VERSION  # the one thing migration changes is the version stamp
    legacy.version += 1  # and the rewrite as JSON is itself a save, which counts
    expected = session_codec.encode(legacy)
    migrated = reload(sid)
    assert migrated is not None and session_codec.encode(migrated) == expected
    assert path.read_bytes()[:1] == b"{" and json.loads(path.read_bytes())["schema_version"] == SessionManager.SCHEMA_VERSION  # rewritten in the new format
    assert {i.concept for i in migrated.paper.study_progress if i.completed} == {"Probability"} and migrated.quiz_attempts
    assert client.get(f"/api/session/{sid}").json()["readiness"]["completed_concepts"] == 1


def test_an_older_file_is_kept_when_its_json_cannot_be_shown_to_match(saved, monkeypatch):
    sid, path = saved
    legacy = session_manager.get(sid)
    legacy.schema_version = 3
    path.write_bytes(pickle.dumps(legacy))
    session_manager.sessions.clear()
    monkeypatch.setattr(session_codec, "loads", lambda raw: (_ for _ in ()).throw(SessionFormatError("simulated")))
    assert session_manager.get(sid) is not None  # still works from the old file
    assert path.read_bytes()[:1] != b"{"  # and the old file is untouched


def test_an_interrupted_write_leaves_the_previous_session_intact(saved, monkeypatch):
    sid, path = saved
    session = session_manager.get(sid)
    good = path.read_bytes()
    session.report["marker"] = "newer"
    with monkeypatch.context() as patched:
        patched.setattr(Path, "replace", lambda self, target: (_ for _ in ()).throw(OSError("disk went away")))
        assert session_manager.save(session) is False and path.read_bytes() == good  # the swap never happened
    with monkeypatch.context() as patched:
        patched.setattr(session_codec, "dumps", lambda *a, **k: (_ for _ in ()).throw(TypeError("halfway")))
        assert session_manager.save(session) is False and path.read_bytes() == good
    assert not list(path.parent.glob("*.tmp"))  # no half-written leftovers
    assert reload(sid).report.get("marker") is None  # the file still holds the last good state


def test_a_truncated_file_reads_as_unreadable_not_as_a_partial_session(saved):
    sid, path = saved
    path.write_bytes(path.read_bytes()[:-200])
    session_manager.sessions.clear()
    assert session_manager.get(sid) is None and session_manager.is_unreadable(sid)
    response = client.get(f"/api/session/{sid}")
    assert response.status_code == 404 and "could not be restored" in response.json()["detail"]


def hostile(name):
    return lambda e: e["session"]["f"]["paper"].update({"__t__": "dc", "c": name, "f": {}})


@pytest.mark.parametrize("change", [
    lambda e: e.update(format="other"), lambda e: e.update(schema_version=3), lambda e: e.update(schema_version=6), lambda e: e.update(schema_version=0),
    lambda e: e.update(schema_version=True), lambda e: e.update(schema_version="4"), lambda e: e.pop("schema_version"), lambda e: e.pop("session"),
    lambda e: e.update(session=[1, 2]), lambda e: e["session"].update(c="backend.models.paper.Paper"),  # a Paper where a session belongs
    lambda e: e["session"]["f"].update(report=[1]), lambda e: e["session"]["f"].update(session_id="another-id"),
    lambda e: e["session"]["f"].update(paper={"__t__": "dc", "c": "backend.models.paper.Prerequisite", "f": {}}),
    hostile("os.system"), hostile("builtins.eval"), hostile("subprocess.Popen"), hostile("backend.nonexistent.Thing"),
    hostile("backend.session.session_manager.SessionManager"),  # a project class, but not saved data
    hostile("backend.models.paper.Nope"), hostile("backend.models.Paper.x.y"),
    lambda e: e["session"]["f"].update(paper={"__t__": "dc", "c": "backend.models.paper.Paper", "f": {"__class__": 1}}),
    lambda e: e["session"]["f"].update(paper={"__t__": "dc", "c": "backend.models.paper.Paper", "f": {"x y": 1}}),
    lambda e: e["session"]["f"].update(paper={"__t__": "mystery"}), lambda e: e["session"]["f"].update(paper={"__t__": "tuple", "v": 3}),
    lambda e: e["session"]["f"].update(paper={"__t__": "float", "v": "banana"}), lambda e: e["session"]["f"].update(paper={"__t__": "enum", "c": "os.name", "v": "x"}),
    lambda e: e["session"]["f"].update(paper={"__t__": "set", "v": [[1]]}),
])
def test_malformed_unsupported_and_hostile_files_are_refused(saved, change):
    sid, path = saved
    edit_json(path, change)
    assert session_manager.get(sid) is None and session_manager.is_unreadable(sid)


@pytest.mark.parametrize("raw", [b"", b"{", b'{"format": "prereqai-session", "schema_version": NaN}', b"[]", b"null", b"\xff\xfe\x00", b"not json", b'{"a":' * 5000])
def test_files_that_are_not_valid_json_envelopes_are_refused(saved, raw):
    sid, path = saved
    path.write_bytes(raw)
    session_manager.sessions.clear()
    assert session_manager.get(sid) is None and session_manager.is_unreadable(sid)


def test_a_deeply_nested_file_is_refused_without_exhausting_the_stack(saved):
    sid, path = saved
    nested = []
    for _ in range(300):
        nested = [nested]
    edit_json(path, lambda e: e["session"]["f"].update(report={"x": nested}))
    assert session_manager.get(sid) is None and session_manager.is_unreadable(sid)


def test_missing_fields_get_their_defaults_and_unknown_ones_are_kept(saved):
    sid, path = saved

    def change(envelope):
        paper = envelope["session"]["f"]["paper"]["f"]
        del paper["hours_per_day"], paper["unrecognised_terms"]  # fields an older file lacks
        paper["added_by_a_later_version"] = {"keep": "me"}  # a field this version does not know
        envelope["session"]["f"]["learning_gaps_extra"] = [1]

    edit_json(path, change)
    session = session_manager.get(sid)
    assert session is not None and session.paper.hours_per_day == 3.0 and session.paper.unrecognised_terms == []
    assert session.paper.added_by_a_later_version == {"keep": "me"} and session.learning_gaps_extra == [1]
    assert client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Probability"}).status_code == 200
    assert json.loads(path.read_bytes())["session"]["f"]["paper"]["f"]["added_by_a_later_version"] == {"keep": "me"}  # and re-saving keeps it


def test_a_json_file_without_a_field_added_without_a_version_bump_still_rebuilds_its_report(saved):
    sid, path = saved
    edit_json(path, lambda e: [item["f"].pop("sections") for item in e["session"]["f"]["paper"]["f"]["missing_prerequisites"]])
    assert client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Probability"}).status_code == 200
