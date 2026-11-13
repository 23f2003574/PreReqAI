"""Saved sessions carry a schema version; older files are upgraded on load and unusable ones read as unreadable, never as an AttributeError later."""
import pickle
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import Prerequisite
from backend.platform import platform
from backend.session import session_manager
from backend.session.session_manager import SessionManager, _fill_new_fields

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
client = TestClient(app, raise_server_exceptions=False)
LATE_FIELDS = {"evidence", "unrecognised_terms", "concepts_without_rules", "schedule"}  # added after the first saved sessions


@pytest.fixture
def saved(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    sid = platform.analyze(SAMPLE)["session_id"]
    yield sid, tmp_path / f"{sid}.session"
    session_manager.sessions.clear()


def rewrite(path, change):
    session = pickle.loads(path.read_bytes())
    change(session)
    path.write_bytes(pickle.dumps(session))
    session_manager.sessions.clear()


def make_legacy(session):
    """What a file written before the late fields existed holds: no schema_version, and no attribute for fields with default factories."""
    del session.__dict__["schema_version"]
    seen = set()

    def strip(item):
        if id(item) in seen:
            return
        seen.add(id(item))
        if hasattr(item, "__dataclass_fields__") and not isinstance(item, type):
            for name in LATE_FIELDS:
                item.__dict__.pop(name, None)
            for value in list(item.__dict__.values()):
                strip(value)
        elif isinstance(item, (list, tuple)):
            for value in item:
                strip(value)

    strip(session.paper)


def test_a_saved_session_is_stamped_with_the_current_version_and_loads(saved):
    sid, path = saved
    assert pickle.loads(path.read_bytes()).schema_version == SessionManager.SCHEMA_VERSION
    session_manager.sessions.clear()
    assert session_manager.get(sid).session_id == sid and not session_manager.is_unreadable(sid)


def test_the_older_file_format_lacks_the_new_fields_that_later_requests_read(saved):
    """The reproduction: a session saved before `evidence` existed raised AttributeError (HTTP 500) when its progress changed."""
    sid, path = saved
    rewrite(path, make_legacy)
    session = pickle.loads(path.read_bytes())
    assert "schema_version" not in session.__dict__ and "evidence" not in session.paper.prerequisites[0].__dict__
    with pytest.raises(AttributeError):
        session.paper.prerequisites[0].evidence


def test_an_older_file_is_upgraded_and_keeps_working(saved):
    sid, path = saved
    rewrite(path, make_legacy)
    assert session_manager.get(sid) is not None
    migrated = session_manager.get(sid)
    assert migrated.schema_version == SessionManager.SCHEMA_VERSION and migrated.paper.prerequisites[0].evidence == []
    assert migrated.paper.unrecognised_terms == [] and migrated.paper.study_time.schedule == []
    assert client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Probability"}).status_code == 200
    assert client.post(f"/api/prerequisites/sessions/{sid}/known", params={"concept": "Calculus"}).status_code == 200
    assert client.post(f"/api/session/{sid}/question", json={"question": "What should I learn first?"}).status_code == 200


def test_a_migrated_session_still_exports_and_resumes_its_plan(saved, tmp_path):
    sid, path = saved
    rewrite(path, make_legacy)
    client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Probability"})
    plan = client.get(f"/api/session/{sid}/plan")
    assert plan.status_code == 200 and "- [x] 2. Probability" in plan.text
    resumed = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", Path(SAMPLE).read_bytes(), "application/pdf"),
                                                              "resume": ("plan.md", plan.content, "text/markdown")})
    assert resumed.status_code == 200
    assert {s["concept"] for s in resumed.json()["report"]["study_progress"] if s["completed"]} == {"Probability"}


@pytest.mark.parametrize("version", [0, 3, 99, -1, "2", None, True, 1.5])
def test_an_unsupported_version_is_unreadable_with_a_clear_error(saved, version):
    sid, path = saved
    rewrite(path, lambda session: setattr(session, "schema_version", version))
    assert session_manager.get(sid) is None and session_manager.is_unreadable(sid)
    response = client.get(f"/api/session/{sid}")
    assert response.status_code == 404 and "could not be restored" in response.json()["detail"] and "another version" in response.json()["hint"]


def test_a_file_that_cannot_be_upgraded_is_unreadable_not_half_loaded(saved):
    sid, path = saved

    def break_it(session):
        make_legacy(session)
        del session.paper.prerequisites[0].__dict__["concept"]  # a field with no default: nothing to restore it from

    rewrite(path, break_it)
    assert session_manager.get(sid) is None and session_manager.is_unreadable(sid)


@pytest.mark.parametrize("content", [b"", b"not a pickle", b"\x80\x04\x95garbage"])
def test_a_corrupted_file_is_unreadable(saved, content):
    sid, path = saved
    path.write_bytes(content)
    session_manager.sessions.clear()
    assert session_manager.get(sid) is None and session_manager.is_unreadable(sid)


def test_restricted_unpickling_still_refuses_foreign_classes(saved):
    import os

    class Evil:
        def __reduce__(self):
            return (os.system, ("echo pwned",))

    sid, path = saved
    path.write_bytes(pickle.dumps(Evil()))
    session_manager.sessions.clear()
    assert session_manager.get(sid) is None and session_manager.is_unreadable(sid)


def test_filling_new_fields_leaves_existing_values_alone():
    item = Prerequisite(concept="Calculus", reason="r", confidence=0.5, evidence=[{"concept": "x"}])
    assert _fill_new_fields(item) is True and item.evidence == [{"concept": "x"}]
